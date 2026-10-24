"""Config flow for Eleven Energy integration."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientSession
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_entry_oauth2_flow

from .const import BASE_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("token", description="API Token"): str,
    }
)


class TokenChecker:
    """Placeholder class to make tests pass.

    TODO Remove this placeholder class and replace with things from your PyPI package.
    """

    def __init__(self, token: str) -> None:
        """Initialize."""
        self.headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def checkToken(self) -> bool:
        """Test we can access the configured host."""
        try:
            async with ClientSession().get(
                BASE_URL + "site", headers=self.headers
            ) as resp:
                _LOGGER.error("Got response %s of %s", resp.url, resp.status)
                return resp.status == 200
        except:  # noqa: E722
            return False


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    hub = TokenChecker(data["token"])

    if not await hub.checkToken():
        raise CannotConnect

    # Return info that you want to store in the config entry.
    return {"title": "Eleven Energy"}


class ConfigFlow(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle a config flow for Eleven Energy.

    Two ways in. Signing in is the one to prefer: the person authenticates on our own page,
    chooses which system to share and names the connection, and Home Assistant never handles a
    credential they typed. An API key is still offered because it is the right answer for a
    headless setup, and because everyone already running has one.
    """

    DOMAIN = DOMAIN
    VERSION = 1

    @property
    def logger(self) -> logging.Logger:
        """Return the logger, as the OAuth flow handler requires."""
        return _LOGGER

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Offer the choice between signing in and pasting a key."""

        entries = self.hass.config_entries.async_entries(DOMAIN)
        if entries:
            return self.async_abort(reason="already_setup")

        return self.async_show_menu(step_id="user", menu_options=["auth", "token"])

    async def async_oauth_create_entry(self, data: dict) -> FlowResult:
        """Finish a sign-in.

        data carries the token Home Assistant obtained and the implementation that obtained it,
        both of which it needs later to refresh. Stored as given.
        """
        return self.async_create_entry(title="Eleven Energy", data=data)

    async def async_step_token(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Set up with an API key instead of signing in."""

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="token", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class OptionsFlowHandler(OptionsFlow):
    """Eleven Energy Options Flow handler.

    No __init__ and no config_entry assignment. Home Assistant sets config_entry
    on the options flow itself, and since it became a read-only property an
    integration assigning it raises - which is the 500 the configuration dialog
    was showing (issue #3).
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Eleven Energy Options Flow handler intiialiser."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # self.config_entry.version = 1
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=user_input,
                    options=self.config_entry.options,
                    title="Eleven Energy",
                )
                return self.async_create_entry(
                    title="Eleven Energy",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("token", default=self.config_entry.data["token"]): str,
                }
            ),
            errors=errors,
        )
