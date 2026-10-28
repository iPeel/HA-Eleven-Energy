"""A class to manage an Inverter."""

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    PERCENTAGE,
    UnitOfElectricCurrent,
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
        summary: dict,
        state: dict | None = None,
    ) -> None:
        """Create an inverter from its site listing and, where we have one, its first reading.

        The listing says what the machine is - three phase, dual battery, its ratings - and the
        reading says how this particular one is put together, which is a different question: a
        dual battery model with one battery fitted is ordinary. Entities are built from both, so
        a single phase system is never given three phases' worth of entities that read zero.
        """
        state = state or {}
        model = summary.get("model") or state.get("model") or {}
        configuration = state.get("configuration") or {}

        self.model = model
        self.configuration = configuration

        # The product name as the machine reports it. The device's own "name" field is a
        # provisioning default that was never corrected per model - every machine carries the
        # same one - so it is a fallback for a portal too old to send the model block, nothing
        # more.
        model_name = model.get("name") or summary.get("name") or "Eleven Energy"

        self.type = "hybridinverter"
        self.device_id = device_id
        self.model_number = model_name
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            name="Eleven Energy " + model_name,
            manufacturer="Eleven Energy",
            model=model_name,
            serial_number=summary.get("serialNumber", ""),
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
                category=EntityCategory.DIAGNOSTIC,
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
                category=EntityCategory.DIAGNOSTIC,
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
            "status": InverterSensorEntity(
                hass,
                device_info=self.device_info,
                device_id=self.device_id,
                entity_type="system_status",
                icon="mdi:check-network-outline",
                device_class=None,
                unit_of_measurement=None,
                state_class=None,
                category=EntityCategory.DIAGNOSTIC,
            ),
        }
        self.binary_sensor_entities = {
            "online": InverterBinarySensorEntity(
                hass,
                device_info=self.device_info,
                device_id=self.device_id,
                device_class=BinarySensorDeviceClass.CONNECTIVITY,
                category=EntityCategory.DIAGNOSTIC,
                entity_type="system_online",
                icon="mdi:cloud-check-variant",
            )
        }

        # Only what this machine actually has. Everything above exists on every inverter; what
        # follows depends on the hardware, and creating it regardless would leave single phase
        # systems with three phases of entities reading zero.
        if model.get("threePhase"):
            # Each group's phases sit wherever that group's own reading sits. Grid power is a
            # headline figure, so its phases are too; system power is diagnostic, so splitting it
            # into three non-diagnostic entities would have scattered one measurement across two
            # sections of the device page.
            self.add_phase_entities(hass, "grid", "mdi:transmission-tower", None)
            self.add_phase_entities(
                hass, "system", "mdi:flash", EntityCategory.DIAGNOSTIC
            )

        for index in range(1, self.mppt_count(model) + 1):
            self.add_mppt_entities(hass, index)

        for index in range(1, self.battery_count(state) + 1):
            self.add_battery_entities(hass, index)

        self.add_rating_entities(hass, model)

    @staticmethod
    def battery_count(state: dict) -> int:
        """How many battery arrays this system reports.

        From the reading rather than the model: the model says how many arrays are supported, and
        a system with one fitted is ordinary. Two batteries behind a single shared BMS are
        reported by the machine as one, which is the truth about what can be seen.
        """
        batteries = (state.get("battery") or {}).get("batteries")
        return len(batteries) if isinstance(batteries, list) else 0

    def add_phase_entities(
        self, hass: HomeAssistant, group: str, icon: str, category
    ) -> None:
        """Add per-phase readings for a group, on three phase machines only.

        category is the one the group's headline reading uses, so the per-phase figures keep it
        company rather than appearing in a different part of the page from the total they add up
        to. Voltage and current are diagnostic either way - they describe the supply rather than
        what the system is doing with it.
        """
        for phase in ("L1", "L2", "L3"):
            lower = phase.lower()

            self.sensor_entities[group + ".phases." + phase + ".power"] = InverterSensorEntity(
                hass,
                device_info=self.device_info,
                device_id=self.device_id,
                entity_type=group + "_power_" + lower,
                unit_of_measurement=UnitOfPower.KILO_WATT,
                decimals=2,
                icon=icon,
                category=category,
            )

            self.sensor_entities[group + ".phases." + phase + ".voltage"] = InverterSensorEntity(
                hass,
                device_info=self.device_info,
                device_id=self.device_id,
                entity_type=group + "_voltage_" + lower,
                unit_of_measurement=UnitOfElectricPotential.VOLT,
                device_class=SensorDeviceClass.VOLTAGE,
                decimals=1,
                icon="mdi:sine-wave",
                category=EntityCategory.DIAGNOSTIC,
            )

            self.sensor_entities[group + ".phases." + phase + ".current"] = InverterSensorEntity(
                hass,
                device_info=self.device_info,
                device_id=self.device_id,
                entity_type=group + "_current_" + lower,
                unit_of_measurement=UnitOfElectricCurrent.AMPERE,
                device_class=SensorDeviceClass.CURRENT,
                decimals=2,
                icon="mdi:current-ac",
                category=EntityCategory.DIAGNOSTIC,
            )

    @staticmethod
    def mppt_count(model: dict) -> int:
        """How many solar trackers this machine has.

        A property of the model rather than of the reading: every machine reports three sets of
        registers whether or not it has three trackers. Dual battery models have three inputs,
        the rest have two, and an unrecognised model gets none rather than a guess.
        """
        if not model:
            return 0
        return 3 if model.get("dualBattery") else 2

    def add_mppt_entities(self, hass: HomeAssistant, index: int) -> None:
        """Add one solar tracker's own readings.

        Diagnostic, all three: the combined pv figures are what somebody puts on a dashboard,
        and these are for working out why one string is behaving differently from another -
        shading, a dead panel, a roof facing the wrong way.
        """
        prefix = "pv.mppts." + str(index) + "."
        name = "mppt_" + str(index) + "_"

        self.sensor_entities[prefix + "power"] = InverterSensorEntity(
            hass,
            device_info=self.device_info,
            device_id=self.device_id,
            entity_type=name + "power",
            unit_of_measurement=UnitOfPower.KILO_WATT,
            decimals=3,
            icon="mdi:solar-power-variant",
            category=EntityCategory.DIAGNOSTIC,
        )

        self.sensor_entities[prefix + "voltage"] = InverterSensorEntity(
            hass,
            device_info=self.device_info,
            device_id=self.device_id,
            entity_type=name + "voltage",
            unit_of_measurement=UnitOfElectricPotential.VOLT,
            device_class=SensorDeviceClass.VOLTAGE,
            decimals=1,
            icon="mdi:flash-triangle-outline",
            category=EntityCategory.DIAGNOSTIC,
        )

        self.sensor_entities[prefix + "current"] = InverterSensorEntity(
            hass,
            device_info=self.device_info,
            device_id=self.device_id,
            entity_type=name + "current",
            unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            device_class=SensorDeviceClass.CURRENT,
            decimals=2,
            icon="mdi:current-dc",
            category=EntityCategory.DIAGNOSTIC,
        )

    def add_battery_entities(self, hass: HomeAssistant, index: int) -> None:
        """Add one battery array's own readings."""
        prefix = "battery.batteries." + str(index) + "."
        name = "battery_" + str(index) + "_"

        # Raw from the BMS, before the top and bottom buffer allowances. It will not agree with
        # the pack's state of charge above, which is the usable figure, so it is named to keep
        # the two apart rather than looking like a rounding error.
        self.sensor_entities[prefix + "stateOfCharge"] = InverterSensorEntity(
            hass,
            device_info=self.device_info,
            device_id=self.device_id,
            entity_type=name + "raw_state_of_charge",
            unit_of_measurement=PERCENTAGE,
            decimals=0,
            icon="mdi:battery-heart-variant",
            device_class=SensorDeviceClass.BATTERY,
            category=EntityCategory.DIAGNOSTIC,
        )

        self.sensor_entities[prefix + "power"] = InverterSensorEntity(
            hass,
            device_info=self.device_info,
            device_id=self.device_id,
            entity_type=name + "power",
            unit_of_measurement=UnitOfPower.KILO_WATT,
            decimals=2,
            icon="mdi:battery-charging",
            category=EntityCategory.DIAGNOSTIC,
        )

        self.sensor_entities[prefix + "moduleCount"] = InverterSensorEntity(
            hass,
            device_info=self.device_info,
            device_id=self.device_id,
            entity_type=name + "modules",
            unit_of_measurement=None,
            device_class=None,
            state_class=None,
            decimals=0,
            icon="mdi:battery-sync",
            category=EntityCategory.DIAGNOSTIC,
        )

    def add_rating_entities(self, hass: HomeAssistant, model: dict) -> None:
        """Add the machine's nameplate ratings, where it reports them.

        Static, but worth having: an automation capping a charge rate wants to know what the
        machine can actually do rather than carrying a number somebody typed once.
        """
        for field, entity_type, icon in (
            ("maxAcPower", "rated_ac_power", "mdi:transmission-tower"),
            ("maxDcPower", "rated_dc_power", "mdi:battery-charging-high"),
        ):
            if field not in model:
                continue

            self.sensor_entities["model." + field] = InverterSensorEntity(
                hass,
                device_info=self.device_info,
                device_id=self.device_id,
                entity_type=entity_type,
                unit_of_measurement=UnitOfPower.KILO_WATT,
                decimals=1,
                icon=icon,
                state_class=None,
                category=EntityCategory.DIAGNOSTIC,
            )

    def processHive(self, json, hive: str):
        """Look for useful content within a sub object in the payload and updates sensors from it."""
        if hive not in json:
            return

        inner = json[hive]

        for key in inner:
            sensor_key = hive + "." + key
            
            val = inner[key]
            if isinstance(val, str):
                val = val.lower()
                
            if sensor_key in self.sensor_entities:
                self.sensor_entities[sensor_key].set_native_value(val)

    def process_phases(self, json, group: str):
        """Update per-phase readings for a group.

        A no-op on a single phase machine, where the entities were never created - and the
        payload carries no phases either, because the API only reports them where there are
        really three.
        """
        phases = (json.get(group) or {}).get("phases")
        if not isinstance(phases, dict):
            return

        for phase, readings in phases.items():
            if not isinstance(readings, dict):
                continue
            for field, value in readings.items():
                key = group + ".phases." + phase + "." + field
                if key in self.sensor_entities:
                    self.sensor_entities[key].set_native_value(value)

    def process_mppts(self, json):
        """Update each solar tracker's readings.

        Keyed on the tracker's own index rather than its position in the list, so a payload that
        ever omits one does not shift another's readings onto it.
        """
        mppts = (json.get("pv") or {}).get("mppts")
        if not isinstance(mppts, list):
            return

        for mppt in mppts:
            if not isinstance(mppt, dict):
                continue
            index = mppt.get("index")
            if index is None:
                continue
            for field, value in mppt.items():
                key = "pv.mppts." + str(index) + "." + field
                if key in self.sensor_entities:
                    self.sensor_entities[key].set_native_value(value)

    def process_batteries(self, json):
        """Update each battery array's own readings.

        Keyed on the array's own index rather than its position in the list, so a system that
        stops reporting one array does not quietly shift the other one's readings onto it.
        """
        batteries = (json.get("battery") or {}).get("batteries")
        if not isinstance(batteries, list):
            return

        for battery in batteries:
            if not isinstance(battery, dict):
                continue
            index = battery.get("index")
            if index is None:
                continue
            for field, value in battery.items():
                key = "battery.batteries." + str(index) + "." + field
                if key in self.sensor_entities:
                    self.sensor_entities[key].set_native_value(value)

    async def update(self, json):
        """Update sensor values from state."""
        # process useable hives from the json payload
        self.processHive(json, "load")
        self.processHive(json, "battery")
        self.processHive(json, "pv")
        self.processHive(json, "grid")
        self.processHive(json, "system")
        self.processHive(json, "operatingMode")

        self.process_phases(json, "grid")
        self.process_phases(json, "system")
        self.process_mppts(json)
        self.process_batteries(json)
        self.processHive(json, "model")

        self.sensor_entities["status"].set_native_value(json["status"].lower())

        self.binary_sensor_entities["online"].set_binary_value(json["online"])


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


class InverterBinarySensorEntity(BinarySensorEntity):
    """A binary sensor for inverter entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        device_info: DeviceInfo,
        device_id: str,
        entity_type,
        icon,
        category=None,
        device_class=None,
    ) -> None:
        """Init binary sensor entity."""
        self.currentValue = None
        self._attr_device_info = device_info
        self.hass = hass
        # binary_sensor, not sensor. This is added through the binary_sensor platform, so minting
        # an id in the sensor domain gave Home Assistant an entity whose id contradicted its own
        # platform - which it warns about now and refuses from 2027.5 (issue #2).
        entity_id = generate_entity_id(
            "binary_sensor.{}",
            device_id + "_" + entity_type,
            [],
            hass,
        )
        self.entity_id = entity_id
        self._attr_has_entity_name = True

        self._attr_translation_key: str = entity_type.lower()
        self._attr_unique_id = device_id + "_" + entity_type

        self._attr_is_on = False
        self.currentValue = False

        self._attr_native_device_class = device_class
        self._attr_device_class = device_class

        self._attr_icon = icon

        if category is not None:
            self._attr_entity_category = category

    def set_binary_value(self, new_state: bool) -> None:
        """Set the HomeAssistant sensor based on inverter."""
        newValue = new_state

        if self.currentValue is not None and self.currentValue == newValue:
            # avoid noise...
            return

        self._attr_is_on = newValue
        self.currentValue = newValue

        self._async_write_ha_state()
