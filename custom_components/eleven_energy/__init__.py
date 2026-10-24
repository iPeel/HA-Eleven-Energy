"""The Eleven Energy integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    config_validation as cv,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORMS
from .controller import Controller
from .oauth import async_register_implementation

_LOGGER = logging.getLogger(__name__)

ISSUE_BINARY_SENSOR_RENAMED = "binary_sensor_renamed"

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

    # Before the platforms add anything: the registry decides an entity's id, so the old one has
    # to be corrected while nothing is holding it.
    migrate_binary_sensor_ids(hass, controller)

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


@callback
def migrate_binary_sensor_ids(hass: HomeAssistant, controller: Controller) -> None:
    """Move binary sensors registered in the sensor domain to where they belong.

    Early releases minted these ids in the sensor domain, so an installation that has been
    running since then holds an entity whose id contradicts the platform that owns it. Correcting
    what the integration asks for does not help those: the registry reuses the id it already has,
    so the mismatch - and Home Assistant's warning about it - survives until the stored id is
    changed, and Home Assistant stops accepting it altogether in 2027.5.

    Renaming does not follow the entity into automations, scripts, dashboards or templates. That
    is why this raises a repair issue naming every id it changed, rather than doing it quietly:
    it breaks once, now, with an explanation, instead of breaking later on an upgrade nobody
    connected it to.
    """
    registry = er.async_get(hass)
    renamed: list[str] = []

    for device in controller.devices.values():
        for entity in device.binary_sensor_entities.values():
            unique_id = entity.unique_id
            if unique_id is None:
                continue

            # Registered under "sensor" is the broken case; anything else is already right.
            old_entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
            if old_entity_id is None:
                continue

            new_entity_id = "binary_sensor." + old_entity_id.split(".", 1)[1]

            try:
                if registry.async_get(new_entity_id) is not None:
                    # Something already holds the correct id - most likely a half-finished
                    # earlier attempt. Drop the stale entry and let the platform register
                    # cleanly rather than trying to merge two.
                    registry.async_remove(old_entity_id)
                else:
                    registry.async_update_entity(
                        old_entity_id, new_entity_id=new_entity_id
                    )
            except (ValueError, KeyError):
                # Some versions refuse a rename that changes the domain. Removing the entry has
                # the same outcome: the platform registers it again, correctly, a moment later.
                _LOGGER.debug(
                    "Could not rename %s, removing it so it registers correctly",
                    old_entity_id,
                )
                registry.async_remove(old_entity_id)

            _LOGGER.info("Renamed %s to %s", old_entity_id, new_entity_id)
            renamed.append(old_entity_id + " → " + new_entity_id)

    if not renamed:
        # Nothing to say, and anything said earlier no longer applies.
        ir.async_delete_issue(hass, DOMAIN, ISSUE_BINARY_SENSOR_RENAMED)
        return

    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_BINARY_SENSOR_RENAMED,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_BINARY_SENSOR_RENAMED,
        translation_placeholders={"entities": "\n".join(renamed)},
        learn_more_url="https://github.com/iPeel/HA-Eleven-Energy/issues/2",
    )


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
