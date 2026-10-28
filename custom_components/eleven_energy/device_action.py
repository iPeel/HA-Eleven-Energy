"""Device actions for Eleven Energy inverters.

These are what appear when somebody builds an automation, picks a device and is offered a list of
things it can do - rather than having to know an action exists and then point it at a machine.

Each one delegates to the matching eleven_energy action, so there is one implementation of what a
work mode means and this is a second way of reaching it. Anything already written against the
actions keeps working untouched.
"""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_TYPE
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    selector,
)
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# A list rather than a set: this is the order they are offered in, and a set would shuffle them
# between restarts. Ordered as somebody would reach for them - the everyday modes first, handing
# control back last.
ACTION_TYPES = [
    "self_consumption",
    "force_charge",
    "grid_export",
    "pv_export",
    "idle_battery",
    "target_soc",
    "reset",
]

# The fields are validated by the action's own schema when it is called, so they are optional
# here; which ones actually apply is decided by async_get_action_capabilities.
ACTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(ACTION_TYPES),
        vol.Optional("target_power"): vol.Coerce(float),
        vol.Optional("target_percent"): vol.Coerce(float),
        vol.Optional("percent_to_battery"): vol.Coerce(float),
        vol.Optional("target_soc"): vol.Coerce(float),
        vol.Optional("target_minutes"): vol.Coerce(int),
        vol.Optional("max_charge_power"): vol.Coerce(float),
        vol.Optional("max_discharge_power"): vol.Coerce(float),
        vol.Optional("allow_charging"): cv.boolean,
        vol.Optional("allow_discharging"): cv.boolean,
        vol.Optional("include_excess_solar"): cv.boolean,
        vol.Optional("overdrive"): cv.boolean,
    }
)


def _percentage(unit: str = "%") -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0, max=100, step=1, unit_of_measurement=unit, mode=selector.NumberSelectorMode.SLIDER
        )
    )


def _power() -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0, max=20, step=0.1, unit_of_measurement="kW", mode=selector.NumberSelectorMode.BOX
        )
    )


async def async_get_actions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List the actions an Eleven Energy inverter offers."""

    registry = er.async_get(hass)
    entries = er.async_entries_for_device(registry, device_id)

    # Debug rather than silence: when these actions do not appear in the user interface, the first
    # thing worth knowing is whether Home Assistant asked us for them at all. No line here means it
    # never called, and nothing we return would have changed that.
    _LOGGER.debug(
        "Device actions asked for %s: %d registry entries, platforms %s",
        device_id,
        len(entries),
        sorted({entry.platform for entry in entries}),
    )

    # Ours is an integration domain rather than an entity domain, so the test is which integration
    # put the entity there - not what kind of entity it is.
    if not any(entry.platform == DOMAIN for entry in entries):
        _LOGGER.debug("No %s entity on device %s, so offering no actions", DOMAIN, device_id)
        return []

    return [
        {CONF_DEVICE_ID: device_id, CONF_DOMAIN: DOMAIN, CONF_TYPE: action_type}
        for action_type in ACTION_TYPES
    ]


async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    context: Context | None,
) -> None:
    """Run a device action by calling the action behind it."""

    action_type = config[CONF_TYPE]

    service_data = {CONF_DEVICE_ID: [config[CONF_DEVICE_ID]]}
    for field, value in config.items():
        if field in (CONF_DEVICE_ID, CONF_DOMAIN, CONF_TYPE, "metadata"):
            continue
        service_data[field] = value

    await hass.services.async_call(
        DOMAIN,
        "set_work_mode_" + action_type,
        service_data,
        blocking=True,
        context=context,
    )


async def async_get_action_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """The fields a given action asks for.

    Mirrors what the action itself accepts, so a device action offers the same choices as calling
    it directly - a percentage slider, a power in kW, rather than a free text box.
    """

    action_type = config[CONF_TYPE]
    fields: dict[vol.Marker, object] = {}

    if action_type == "self_consumption":
        fields[vol.Optional("percent_to_battery")] = _percentage()

    elif action_type == "force_charge":
        fields[vol.Required("target_power")] = _power()
        fields[vol.Required("target_percent")] = _percentage()

    elif action_type == "grid_export":
        fields[vol.Required("target_power")] = _power()
        fields[vol.Required("target_percent")] = _percentage()
        fields[vol.Optional("include_excess_solar")] = selector.BooleanSelector()
        fields[vol.Optional("overdrive")] = selector.BooleanSelector()

    elif action_type == "idle_battery":
        fields[vol.Optional("allow_charging")] = selector.BooleanSelector()
        fields[vol.Optional("allow_discharging")] = selector.BooleanSelector()

    elif action_type == "target_soc":
        fields[vol.Required("target_soc")] = _percentage()
        fields[vol.Required("target_minutes")] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=5, max=1440, step=5, unit_of_measurement="min", mode=selector.NumberSelectorMode.BOX
            )
        )
        fields[vol.Optional("max_charge_power")] = _power()
        fields[vol.Optional("max_discharge_power")] = _power()

    # pv_export and reset take nothing.

    return {"extra_fields": vol.Schema(fields)}
