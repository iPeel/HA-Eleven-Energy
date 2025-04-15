"""Eleven Energy Sensor init."""

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensor platform."""
    controller = hass.data[DOMAIN]["controller"]
    for inverter in controller.devices.values():
        async_add_entities(list(inverter.sensor_entities.values()))

    controller.complete_platform_setup("seensor")


class InverterSensorEntity(SensorEntity):
    """The main Inverter sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        device_info: DeviceInfo,
        device_id: str,
        entity_type,
        icon,
        unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        decimals=-1,
        category=None,
    ) -> None:
        """Inverter sensor intialiser."""
        self.currentValue = None
        self._attr_device_info = device_info
        self._attr_unique_id = device_id + "_" + entity_type
        entity_id = generate_entity_id(
            "sensor.{}",
            device_id + "_" + entity_type,
            [],
            hass,
        )
        self.entity_id = entity_id

        # self._entity_name = entityName
        # self._attr_name = entity_name
        self._attr_has_entity_name = True

        self._attr_translation_key: str = entity_type.lower()

        self._attr_native_unit_of_measurement = unit_of_measurement
        self._attr_native_device_class = device_class
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_icon = icon

        if state_class == SensorStateClass.TOTAL:
            self._attr_last_reset = 0

        if category is not None:
            self._attr_entity_category = category

        if decimals >= 0:
            self._attr_suggested_display_precision = decimals

    def set_native_value(self, new_state) -> None:
        """Set the HA value from the modbus response."""
        _LOGGER.info("Setting value from %s", new_state)
        if self.currentValue is not None and self.currentValue == new_state:
            # avoid noise...
            return

        self.currentValue = new_state

        self._attr_native_value = new_state
        self.async_write_ha_state()
