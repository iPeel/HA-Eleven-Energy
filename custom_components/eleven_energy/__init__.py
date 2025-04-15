"""The Eleven Energy integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .controller import Controller

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Eleven Energy from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
        hass.data[DOMAIN]["entities"] = []
    _LOGGER.info("*** STARTUP***")

    controller = Controller(entry.data["token"], hass, entry)
    hass.data[DOMAIN]["controller"] = controller
    await controller.initialise()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def setup(hass: HomeAssistant, entry: ConfigEntry):
    """Set up is called when Home Assistant is loading our component."""

    def handle_set_workmode(call):
        controller = hass.data[DOMAIN]["controller"]
        controller.set_work_mode(call.data)

    hass.services.register(DOMAIN, "set_operating_mode", handle_set_workmode)

    _LOGGER.info("Registered Eleven Energy services")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if hass.data[DOMAIN]["controller"] is not None:
        hass.data[DOMAIN]["controller"].terminate()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", entry.version)

    return True
