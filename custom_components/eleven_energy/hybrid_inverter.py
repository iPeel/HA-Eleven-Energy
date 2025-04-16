"""A class to manage an Inverter."""

import logging

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .sensor import InverterSensorEntity

_LOGGER = logging.getLogger(__name__)


class HybridInverter:
    """Inverter object."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, device_id: str) -> None:
        """Create an inverter."""
        self.device_id = device_id
        self.model_number = "North Sea 6"
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            name="Eleven Energy North Sea 6",
            manufacturer="Eleven Energy",
            model=self.model_number,
        )
        self.hass = hass
        self.entry = entry
        self.sensor_entities = {
            "pv.power": InverterSensorEntity(
                hass,
                device_info=self.device_info,
                device_id=self.device_id,
                entity_type="pvPower",
                unit_of_measurement=UnitOfPower.KILO_WATT,
                decimals=2,
                icon="mdi:solar-power",
            ),
            "pv.energyToday": InverterSensorEntity(
                hass,
                device_info=self.device_info,
                device_id=self.device_id,
                entity_type="pvEnergyToday",
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
                entity_type="loadPower",
                unit_of_measurement=UnitOfPower.KILO_WATT,
                decimals=2,
                icon="mdi:home-lightning-bolt",
            ),
            "load.energyToday": InverterSensorEntity(
                hass,
                device_info=self.device_info,
                device_id=self.device_id,
                entity_type="loadEnergyToday",
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
                entity_type="soc",
                unit_of_measurement=PERCENTAGE,
                decimals=0,
                icon="mdi:battery",
                device_class=SensorDeviceClass.BATTERY,
            ),
            "battery.power": InverterSensorEntity(
                hass,
                device_info=self.device_info,
                device_id=self.device_id,
                entity_type="batteryPower",
                unit_of_measurement=UnitOfPower.KILO_WATT,
                decimals=2,
                icon="mdi:battery-minus-variant",
            ),
            "battery.energyInToday": InverterSensorEntity(
                hass,
                device_info=self.device_info,
                device_id=self.device_id,
                entity_type="batteryEnergyInToday",
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
                entity_type="batteryEnergyOutToday",
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
                entity_type="gridPower",
                unit_of_measurement=UnitOfPower.KILO_WATT,
                decimals=2,
                icon="mdi:transmission-tower",
            ),
            "grid.energyInToday": InverterSensorEntity(
                hass,
                device_info=self.device_info,
                device_id=self.device_id,
                entity_type="gridEnergyInToday",
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
                entity_type="gridEnergyOutToday",
                unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                decimals=2,
                icon="mdi:transmission-tower-import",
                device_class=SensorDeviceClass.ENERGY,
                state_class=SensorStateClass.TOTAL_INCREASING,
            ),
        }

    def processHive(self, json, hive: str):
        """Process a hive within the json."""
        if hive not in json:
            return

        inner = json[hive]

        for key in inner:
            sensor_key = hive + "." + key
            if sensor_key in self.sensor_entities:
                _LOGGER.info("Setting sensor %s to %s", sensor_key, inner[key])
                self.sensor_entities[sensor_key].set_native_value(inner[key])

    async def update(self, json):
        """Update sensor values from state."""

        _LOGGER.info("Update %s", json)
        self.processHive(json, "load")
        self.processHive(json, "battery")
        self.processHive(json, "pv")
        self.processHive(json, "grid")
