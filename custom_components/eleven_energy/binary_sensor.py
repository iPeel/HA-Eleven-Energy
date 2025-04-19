"""Eleven Energy Sensor init."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up binary sensor platform."""

    # We'll grab all the devices from the controller, then iterate through and register any sensors within each device.
    controller = hass.data[DOMAIN]["controller"]
    for inverter in controller.devices.values():
        async_add_entities(list(inverter.binary_sensor_entities.values()))

    # Finally, call the controller setup completion so it can start updating sensors.
    controller.complete_platform_setup("binary_sensor")
