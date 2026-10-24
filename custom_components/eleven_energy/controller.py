"""The main Eleven Energy coordinator."""

import asyncio
import logging

from aiohttp import ClientResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry

from .const import BASE_URL, DOMAIN, PLATFORMS, POLL_INTERVAL_SECONDS
from .hybrid_inverter import HybridInverter

_LOGGER = logging.getLogger(__name__)


class Controller:
    """Controller class orchestrating the data fetching and entitities."""

    def __init__(
        self,
        token: str | None,
        hass: HomeAssistant,
        entry: ConfigEntry,
        session: config_entry_oauth2_flow.OAuth2Session | None = None,
    ) -> None:
        """Initialise the controller.

        Either an API key, which never changes, or an OAuth session, whose access token lasts
        eight hours and is refreshed as needed. Headers are built per request for that reason
        rather than once here.
        """
        self.token = token
        self.session = session
        self.hass = hass
        self.config = entry
        self.poller_task = None
        self.devices = {}
        self.platforms_started = 0

    async def auth_headers(self) -> dict:
        """The headers for a call, with a token that is valid now.

        For a signed-in account this refreshes the access token when it is close to expiring,
        which is why every call goes through here instead of reusing a header built at startup.
        """
        if self.session is not None:
            await self.session.async_ensure_token_valid()
            token = self.session.token["access_token"]
        else:
            token = self.token

        return {
            "accept": "application/json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def send_reliable_post(self, url_suffix: str, json: dict) -> ClientResponse:
        """Make multiple attempts to post a request, doubling the delays each time."""
        loops = 1
        while loops <= 32:
            response = await async_get_clientsession(self.hass).post(
                BASE_URL + url_suffix,
                headers=await self.auth_headers(),
                json=json,
            )

            if response.status == 200:
                return response

            _LOGGER.info("Set workmode got status %s", response.status)
            await asyncio.sleep(loops)
            loops = loops * 2

        return response  # return the last received response

    def resolve_device(self, data) -> str | None:
        """Work out which inverter a call is aimed at.

        A device target is the direct route. An entity target is accepted too, because the action
        definition used to offer entities and automations were written against it - the entity is
        looked up to find the device it belongs to. Either way what comes back is the cloud id.
        """
        hass_device_ids = data.get("device_id")
        if isinstance(hass_device_ids, str):
            hass_device_ids = [hass_device_ids]

        if not hass_device_ids:
            entity_ids = data.get("entity_id")
            if isinstance(entity_ids, str):
                entity_ids = [entity_ids]

            if entity_ids:
                ent_reg = er.async_get(self.hass)
                hass_device_ids = []
                for entity_id in entity_ids:
                    entry = ent_reg.async_get(entity_id)
                    if entry is not None and entry.device_id is not None:
                        hass_device_ids.append(entry.device_id)

        if hass_device_ids:
            dev_reg = dr.async_get(self.hass)
            for hass_device_id in hass_device_ids:
                dev: DeviceEntry = dev_reg.async_get(hass_device_id)
                if dev is None:
                    continue
                for identifier in dev.identifiers:
                    if identifier[0] == DOMAIN and identifier[1] in self.devices:
                        return identifier[1]

        # Nothing targeted. One inverter is the common case and picking it is a kindness; more
        # than one and guessing would control the wrong machine, so it is refused instead.
        inverters = [
            device.device_id
            for device in self.devices.values()
            if device.type == "hybridinverter"
        ]

        if len(inverters) == 1:
            return inverters[0]

        if len(inverters) > 1:
            raise ServiceValidationError(
                "This site has more than one inverter, so the action needs a target. "
                "Choose the inverter under Targets, or add a device_id."
            )

        return None

    async def set_work_mode(self, mode, data) -> None:
        """Change the system work mode."""
        device_id = self.resolve_device(data)

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
                # services.yaml offered percentage_to_battery while this read
                # percent_to_battery, so the field never did anything. Both are taken.
                for field in ("percent_to_battery", "percentage_to_battery"):
                    if field in data:
                        params["targetExcessPc"] = data[field]
                        break

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

            case "set_work_mode_target_soc":
                workMode = "targetSoc"
                if "target_soc" in data:
                    params["targetSoc"] = data["target_soc"]
                if "max_charge_power" in data:
                    params["maxChargeRate"] = data["max_charge_power"]
                if "max_discharge_power" in data:
                    params["maxDischargeRate"] = data["max_discharge_power"]
                if "target_minutes" in data:
                    params["targetMinutes"] = data["target_minutes"]
                    
            case "set_work_mode_reset":
                workMode = "reset"

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
                try:
                    await self.poll_devices()
                except:  # noqa: E722
                    _LOGGER.warning("Unable to poll Eleven API")
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
                BASE_URL + "devices/" + device.device_id, headers=await self.auth_headers()
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
            BASE_URL + "site", headers=await self.auth_headers()
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
                # Read the machine once before building its entities. The site listing says what
                # model it is, but how many batteries are actually fitted is only in the reading,
                # and entities are created once at setup - so asking now is the difference
                # between a correct set of entities and a guess.
                state = await self.read_device(device_id)

                inverter = HybridInverter(
                    self.hass,
                    self.config,
                    device_id,
                    device,
                    state,
                )
                self.devices[device_id] = inverter
                _LOGGER.info(
                    "Created inverter %s (%s, %s phase, %s batter%s)",
                    device_id,
                    inverter.model_number,
                    3 if inverter.model.get("threePhase") else 1,
                    HybridInverter.battery_count(state or {}),
                    "y" if HybridInverter.battery_count(state or {}) == 1 else "ies",
                )

    async def read_device(self, device_id: str) -> dict | None:
        """Read one device's state, or None where it cannot be read.

        Used during discovery, where a failure must not stop the integration setting up: the
        inverter is still created from its listing and simply gets the entities the model implies,
        with the per-battery ones appearing after a restart once it answers.
        """
        try:
            response = await async_get_clientsession(self.hass).get(
                BASE_URL + "devices/" + device_id, headers=await self.auth_headers()
            )

            if response.status != 200:
                _LOGGER.warning(
                    "Could not read device %s during discovery, status %s",
                    device_id,
                    response.status,
                )
                return None

            return await response.json()
        except Exception:  # noqa: BLE001
            _LOGGER.warning("Could not read device %s during discovery", device_id)
            return None

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
