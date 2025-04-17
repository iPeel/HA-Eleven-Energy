"""A class to manage an Inverter."""

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import generate_entity_id

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class HybridInverter:
    """Inverter object."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device_id: str,
        device_name: str,
        device_serial_number: str,
    ) -> None:
        """Create an inverter."""
        self.type = "hybridinverter"
        self.device_id = device_id
        self.model_number = device_name
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            name="Eleven Energy " + device_name,
            manufacturer="Eleven Energy",
            model=self.model_number,
            serial_number=device_serial_number,
        )
        self.hass = hass
        self.entry = entry
        self.sensor_entities = {
            "pv.power": InverterSensorEntity(
                hass,
                device_info=self.device_info,
                device_id=self.device_id,
                entity_type="pv_power",
                unit_of_measurement=UnitOfPower.KILO_WATT,
                decimals=2,
                icon="mdi:solar-power",
            ),
            "pv.energyToday": InverterSensorEntity(
                hass,
                device_info=self.device_info,
                device_id=self.device_id,
                entity_type="pv_energy_today",
                unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                decimals=2,
                icon="mdi:solar-power-variant",
                device_class=SensorDeviceClass.ENERGY,
                state_class=SensorStateClass.TOTAL_INCREASING,
            ),
            "load.power": InverterSensorEntity(
                hass,
                device_info=self.device_info,
                device_id=self.device_id,
                entity_type="load_power",
                unit_of_measurement=UnitOfPower.KILO_WATT,
                decimals=2,
                icon="mdi:home-lightning-bolt",
            ),
            "load.energyToday": InverterSensorEntity(
                hass,
                device_info=self.device_info,
                device_id=self.device_id,
                entity_type="load_energy_today",
                unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                decimals=2,
                icon="mdi:lightning-bolt",
                device_class=SensorDeviceClass.ENERGY,
                state_class=SensorStateClass.TOTAL_INCREASING,
            ),
            "battery.stateOfCharge": InverterSensorEntity(
                hass,
                device_info=self.device_info,
                device_id=self.device_id,
                entity_type="state_of_charge",
                unit_of_measurement=PERCENTAGE,
                decimals=0,
                icon="mdi:battery",
                device_class=SensorDeviceClass.BATTERY,
            ),
            "battery.power": InverterSensorEntity(
                hass,
                device_info=self.device_info,
                device_id=self.device_id,
                entity_type="battery_power",
                unit_of_measurement=UnitOfPower.KILO_WATT,
                decimals=2,
                icon="mdi:battery-minus-variant",
            ),
            "battery.energyInToday": InverterSensorEntity(
                hass,
                device_info=self.device_info,
                device_id=self.device_id,
                entity_type="battery_energy_in_today",
                unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                decimals=2,
                icon="mdi:battery-plus",
                device_class=SensorDeviceClass.ENERGY,
                state_class=SensorStateClass.TOTAL_INCREASING,
            ),
            "battery.energyOutToday": InverterSensorEntity(
                hass,
                device_info=self.device_info,
                device_id=self.device_id,
                entity_type="battery_energy_out_today",
                unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                decimals=2,
                icon="mdi:battery-minus",
                device_class=SensorDeviceClass.ENERGY,
                state_class=SensorStateClass.TOTAL_INCREASING,
            ),
            "grid.power": InverterSensorEntity(
                hass,
                device_info=self.device_info,
                device_id=self.device_id,
                entity_type="grid_power",
                unit_of_measurement=UnitOfPower.KILO_WATT,
                decimals=2,
                icon="mdi:transmission-tower",
            ),
            "grid.energyInToday": InverterSensorEntity(
                hass,
                device_info=self.device_info,
                device_id=self.device_id,
                entity_type="grid_energy_in_today",
                unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                decimals=2,
                icon="mdi:transmission-tower-export",
                device_class=SensorDeviceClass.ENERGY,
                state_class=SensorStateClass.TOTAL_INCREASING,
            ),
            "grid.energyOutToday": InverterSensorEntity(
                hass,
                device_info=self.device_info,
                device_id=self.device_id,
                entity_type="grid_energy_out_today",
                unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                decimals=2,
                icon="mdi:transmission-tower-import",
                device_class=SensorDeviceClass.ENERGY,
                state_class=SensorStateClass.TOTAL_INCREASING,
            ),
            "system.power": InverterSensorEntity(
                hass,
                device_info=self.device_info,
                device_id=self.device_id,
                entity_type="system_power",
                unit_of_measurement=UnitOfPower.KILO_WATT,
                decimals=2,
                icon="mdi:flash",
            ),
            "system.voltage": InverterSensorEntity(
                hass,
                device_info=self.device_info,
                device_id=self.device_id,
                entity_type="system_voltage",
                unit_of_measurement=UnitOfElectricPotential.VOLT,
                device_class=SensorDeviceClass.VOLTAGE,
                decimals=2,
                icon="mdi:flash",
            ),
            "operatingMode.workMode": InverterSensorEntity(
                hass,
                device_info=self.device_info,
                device_id=self.device_id,
                entity_type="system_work_mode",
                icon="mdi:all-inclusive-box-outline",
                device_class=None,
                unit_of_measurement=None,
                state_class=None,
            ),
        }

    def processHive(self, json, hive: str):
        """Look for useful content within a sub object in the payload and updates sensors from it."""
        if hive not in json:
            return

        inner = json[hive]

        for key in inner:
            sensor_key = hive + "." + key
            if sensor_key in self.sensor_entities:
                self.sensor_entities[sensor_key].set_native_value(inner[key])

    async def update(self, json):
        """Update sensor values from state."""

        # process useable hives from the json payload
        self.processHive(json, "load")
        self.processHive(json, "battery")
        self.processHive(json, "pv")
        self.processHive(json, "grid")
        self.processHive(json, "system")
        self.processHive(json, "operatingMode")


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
        """Set the HA value from the update response."""
        if self.currentValue is not None and self.currentValue == new_state:
            # avoid noise...
            return

        self.currentValue = new_state

        self._attr_native_value = new_state
        self.async_write_ha_state()
