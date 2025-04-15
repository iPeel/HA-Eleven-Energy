"""The main Eleven Energy coordinator."""

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

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

    def set_work_mode(self, data) -> None:
        """Change the system work mode."""

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
                inverter = HybridInverter(self.hass, self.config, device_id)
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
