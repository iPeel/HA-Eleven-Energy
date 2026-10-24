"""The Eleven Energy integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    config_validation as cv,
)
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORMS
from .controller import Controller
from .oauth import async_register_implementation

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required("token", description="API Token"): str,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration itself.

    The OAuth implementation is registered here rather than per config entry, because the config
    flow needs it before there is an entry to attach it to.
    """
    async_register_implementation(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Eleven Energy from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
        hass.data[DOMAIN]["entities"] = []

    # Two shapes of credential. An API key is the string the person pasted in; a signed-in
    # account stores the token as a structure Home Assistant maintains, and the session is what
    # keeps it fresh. The presence of auth_implementation is what tells them apart - it is set
    # only by the OAuth flow.
    if "auth_implementation" in entry.data:
        implementation = (
            await config_entry_oauth2_flow.async_get_config_entry_implementation(
                hass, entry
            )
        )
        session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
        controller = Controller(None, hass, entry, session=session)
    else:
        controller = Controller(entry.data["token"], hass, entry)

    hass.data[DOMAIN]["controller"] = controller
    await controller.initialise()

    register_actions(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


# Every action takes a target, and a target arrives in call.data as device_id, entity_id or
# area_id. Letting those through unvalidated is deliberate - Home Assistant has already resolved
# them - while the action's own fields are checked here, so a percentage of 400 or a power of
# "fast" is refused with a message rather than sent to an inverter.
TARGET_SCHEMA = {
    vol.Optional("device_id"): vol.Any(cv.string, [cv.string]),
    vol.Optional("entity_id"): vol.Any(cv.string, [cv.string]),
    vol.Optional("area_id"): vol.Any(cv.string, [cv.string]),
}

PERCENTAGE = vol.All(vol.Coerce(float), vol.Range(min=0, max=100))
POWER_KW = vol.All(vol.Coerce(float), vol.Range(min=0, max=50))

SERVICE_SCHEMAS = {
    "set_work_mode_self_consumption": vol.Schema(
        {
            **TARGET_SCHEMA,
            vol.Optional("percent_to_battery"): PERCENTAGE,
            # The name services.yaml used to offer. Accepted so anything written against it works.
            vol.Optional("percentage_to_battery"): PERCENTAGE,
        }
    ),
    "set_work_mode_force_charge": vol.Schema(
        {
            **TARGET_SCHEMA,
            vol.Required("target_power"): POWER_KW,
            vol.Required("target_percent"): PERCENTAGE,
        }
    ),
    "set_work_mode_grid_export": vol.Schema(
        {
            **TARGET_SCHEMA,
            vol.Required("target_power"): POWER_KW,
            vol.Required("target_percent"): PERCENTAGE,
            vol.Optional("include_excess_solar"): cv.boolean,
            vol.Optional("overdrive"): cv.boolean,
        }
    ),
    "set_work_mode_pv_export": vol.Schema({**TARGET_SCHEMA}),
    "set_work_mode_idle_battery": vol.Schema(
        {
            **TARGET_SCHEMA,
            vol.Optional("allow_charging"): cv.boolean,
            vol.Optional("allow_discharging"): cv.boolean,
        }
    ),
    "set_work_mode_target_soc": vol.Schema(
        {
            **TARGET_SCHEMA,
            vol.Required("target_soc"): PERCENTAGE,
            vol.Required("target_minutes"): vol.All(vol.Coerce(int), vol.Range(min=1, max=1440)),
            vol.Optional("max_charge_power"): POWER_KW,
            vol.Optional("max_discharge_power"): POWER_KW,
        }
    ),
    "set_work_mode_reset": vol.Schema({**TARGET_SCHEMA}),
}


def register_actions(hass: HomeAssistant) -> None:
    """Register the work mode actions.

    Registered once for the integration rather than per config entry, and guarded so a second
    entry does not re-register them. Names and field names are unchanged from the first release,
    so existing automations and scripts keep working untouched.
    """

    async def handle_set_workmode(call: ServiceCall) -> None:
        controller = hass.data[DOMAIN].get("controller")
        if controller is None:
            raise ServiceValidationError(
                "Eleven Energy is not set up yet, so there is nothing to control."
            )
        await controller.set_work_mode(call.service, call.data)

    for service, schema in SERVICE_SCHEMAS.items():
        if hass.services.has_service(DOMAIN, service):
            continue

        hass.services.async_register(
            DOMAIN,
            service,
            handle_set_workmode,
            schema=schema,
            supports_response=SupportsResponse.NONE,
        )

    _LOGGER.debug("Registered %d Eleven Energy actions", len(SERVICE_SCHEMAS))


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if hass.data[DOMAIN]["controller"] is not None:
        hass.data[DOMAIN]["controller"].terminate()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", entry.version)

    return True
