"""Config flow for Eleven Energy integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aiohttp import ClientSession
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_RECONFIGURE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_entry_oauth2_flow

from .const import BASE_URL, DOMAIN
from .oauth import async_register_implementation

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

        # Registered here as well as at setup of the integration. With no config entry there is
        # nothing to trigger that setup, so on a first install - or after the last entry is
        # deleted - the flow would run with no implementation registered and abort with
        # missing_configuration. Registering is a cheap callback keyed by domain, so doing it
        # twice costs nothing.
        async_register_implementation(self.hass)

        # pick_implementation, not auth. async_step_auth needs flow_impl, and
        # async_step_pick_implementation is what sets it - going straight to auth reaches the
        # authorize step with no implementation chosen and fails on a None. With one
        # implementation registered it selects that one and moves on without asking.
        return self.async_show_menu(
            step_id="user", menu_options=["pick_implementation", "token"]
        )

    async def async_oauth_create_entry(self, data: dict) -> FlowResult:
        """Finish a sign-in.

        data carries the token Home Assistant obtained and the implementation that obtained it,
        both of which it needs later to refresh. Stored as given.
        """
        # Signing in against an entry that already exists - because the credential stopped
        # working, or because somebody chose to change it. Either way the entry keeps its
        # identity, its devices and its entities, and only the credential is replaced. Creating
        # a second entry would orphan every entity on the first.
        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data
            )

        if self.source == SOURCE_RECONFIGURE:
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(), data=data
            )

        return self.async_create_entry(title="Eleven Energy", data=data)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Change how an existing system is connected.

        The same choice as setting up, offered against an entry that already exists - so somebody
        who started with an API key can move to signing in, and somebody signed in can drop back
        to a key for a headless setup. Either way the entry keeps its identity, its devices and
        its entities; only the credential changes.
        """
        async_register_implementation(self.hass)

        return self.async_show_menu(
            step_id="reconfigure", menu_options=["pick_implementation", "token"]
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """The credential stopped working.

        Reached when the API rejects what we hold - a key revoked from the app, one that lapsed
        through disuse, or a withdrawn consent. Which way the person came in originally decides
        what they are asked for: signing in again, or a new key.
        """
        if "auth_implementation" in entry_data:
            async_register_implementation(self.hass)
            return await self.async_step_pick_implementation()

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Take a replacement API key."""

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
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

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
                # Reached from reconfigure, this is somebody moving an existing system onto a
                # key. The entry is updated rather than replaced, and data is set rather than
                # merged - so the token structure left behind by a previous sign-in goes, and
                # the entry does not end up carrying both kinds of credential.
                if self.source == SOURCE_RECONFIGURE:
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(), data=user_input
                    )

                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="token", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )



class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
