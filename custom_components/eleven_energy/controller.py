"""The main Eleven Energy coordinator."""

import asyncio
import logging

from aiohttp import ClientResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry

from .const import BASE_URL, PLATFORMS, POLL_INTERVAL_SECONDS
from .hybrid_inverter import HybridInverter

_LOGGER = logging.getLogger(__name__)


class Controller:
    """Controller class orchestrating the data fetching and entitities."""

    def __init__(self, token: str, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise the controller."""
        self.token = token
        self.hass = hass
        self.config = entry
        self.poller_task = None
        self.headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        self.devices = {}
        self.platforms_started = 0

    async def send_reliable_post(self, url_suffix: str, json: dict) -> ClientResponse:
        """Make multiple attempts to post a request, doubling the delays each time."""
        loops = 1
        while loops <= 32:
            response = await async_get_clientsession(self.hass).post(
                BASE_URL + url_suffix,
                headers=self.headers,
                json=json,
            )

            if response.status == 200:
                return response

            _LOGGER.info("Set workmode got status %s", response.status)
            await asyncio.sleep(loops)
            loops = loops * 2

        return response  # return the last received response

    async def set_work_mode(self, mode, data) -> None:
        """Change the system work mode."""
        device_id = None

        # If a device is specified, find the cloud device ID from the device identifier
        if "device_id" in data:
            hass_device_id = data["device_id"][0]
            dev_reg = dr.async_get(self.hass)
            dev: DeviceEntry = dev_reg.async_get(hass_device_id)
            for identifier in dev.identifiers:
                device_id = identifier[1]

        # If no device specified, find it in our own registry
        if device_id is None:
            for device in self.devices.values():
                if device.type == "hybridinverter":
                    device_id = device.device_id
                    break

        if device_id is None:
            _LOGGER.warning("Cannot perform set workmode as no device determined")
            return

        workMode = None
        params = {}

        # detect supported work modes and extract useful parameters from the data.
        match mode:
            case "set_work_mode_self_consumption":
                _LOGGER.info("Self consumption")
                workMode = "selfConsumption"
                if "percent_to_battery" in data:
                    params["targetExcessPc"] = data["percent_to_battery"]

            case "set_work_mode_force_charge":
                workMode = "forceCharge"
                if "target_percent" in data:
                    params["targetSoc"] = data["target_percent"]
                if "target_power" in data:
                    params["rate"] = data["target_power"]

            case "set_work_mode_grid_export":
                workMode = "gridExport"
                if "target_percent" in data:
                    params["targetSoc"] = data["target_percent"]
                if "target_power" in data:
                    params["rate"] = data["target_power"]
                if "include_excess_solar" in data:
                    params["addAverageExcess"] = data["include_excess_solar"]
                if "overdrive" in data:
                    params["overdrive"] = data["overdrive"]

            case "set_work_mode_pv_export":
                workMode = "pvExportPriority"

            case "set_work_mode_idle_battery":
                workMode = "idleBattery"
                if "allow_charging" in data:
                    params["allowCharge"] = data["allow_charging"]
                if "allow_discharging" in data:
                    params["allowDischarge"] = data["allow_discharging"]

            case _:
                _LOGGER("Unable to determine work mode from %s", mode)
                return

        params["workMode"] = workMode

        response = await self.send_reliable_post(
            "devices/" + device_id + "/operatingMode", params
        )

        if response.status != 200:
            _LOGGER.warning(
                "Unable to change work mode, received status %s", response.status
            )

    async def initialise(self):
        """Set up the controller."""
        _LOGGER.info("Eleven Energy initialising")
        await self.poll_site()

    def start_poller(self):
        """Start the async polling of inverter data."""

        async def periodic():
            while True:
                _LOGGER.debug("Polling Eleven Energy")
                await self.poll_devices()
                await asyncio.sleep(
                    POLL_INTERVAL_SECONDS
                )  # first because we polled it in await after init.

        task = self.config.async_create_background_task(
            self.hass, periodic(), "Eleven Energy Poll"
        )

        self.poller_task = task

    async def poll_devices(self):
        """Poll all devices for updates."""
        for device in self.devices.values():
            response = await async_get_clientsession(self.hass).get(
                BASE_URL + "devices/" + device.device_id, headers=self.headers
            )

            if response.status != 200:
                _LOGGER.warning(
                    "Eleven Energy call to site API responded with %s", response.status
                )
                return

            json = await response.json()
            await device.update(json)

    async def poll_site(self):
        """Poll site for device changes."""
        response = await async_get_clientsession(self.hass).get(
            BASE_URL + "site", headers=self.headers
        )

        if response.status != 200:
            _LOGGER.warning(
                "Eleven Energy call to site API responded with %s", response.status
            )
            return

        js = await response.json()
        for device in js["devices"]:
            device_id = device["deviceId"]
            device_type = device["type"]
            if device_type != "hybridinverter":
                continue
            if device_id not in self.devices:
                inverter = HybridInverter(
                    self.hass,
                    self.config,
                    device_id,
                    device.get("name", "Eleven Energy"),
                    device.get("serialNumber", ""),
                )
                self.devices[device_id] = inverter
                _LOGGER.info("Created inverter %s", device_id)

    def complete_platform_setup(self, platform):
        """Mark a platform as started during init."""
        self.platforms_started = self.platforms_started + 1
        if self.platforms_started == len(PLATFORMS):
            self.start_poller()

    def __del__(self):
        """Log deletion."""
        _LOGGER.debug("Controller deleted")
        self.terminate()

    def terminate(self):
        """End the controller."""
        if self.poller_task is not None:
            self.poller_task.cancel()
            self.poller_task = None
            _LOGGER.info("Eleven Energy is no longer polling")
