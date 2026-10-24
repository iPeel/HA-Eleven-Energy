"""Signing in with an Eleven Energy account."""

from __future__ import annotations

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_entry_oauth2_flow

from .const import (
    DOMAIN,
    OAUTH_AUTHORIZE_URL,
    OAUTH_CLIENT_ID,
    OAUTH_TOKEN_URL,
    SCOPES_FULL,
)


class ElevenEnergyOAuth2Implementation(
    config_entry_oauth2_flow.LocalOAuth2ImplementationWithPkce
):
    """The Eleven Energy OAuth client, which has no secret.

    Home Assistant's usual arrangement asks the person to create their own OAuth client and paste
    its id and secret in. That is the right answer where a secret is meaningful, and the wrong one
    here: everybody installing this integration would be registering a client for a service they
    do not run, to obtain a secret that would then sit in their config directory.

    Instead the integration carries a public client id and no secret, which is honest about what a
    published application can keep, and the authorization server requires PKCE from it - so an
    intercepted code is useless to anyone who did not start the flow.
    """

    def __init__(self, hass: HomeAssistant, scopes: list[str] | None = None) -> None:
        """Create the implementation."""
        super().__init__(
            hass,
            DOMAIN,
            OAUTH_CLIENT_ID,
            OAUTH_AUTHORIZE_URL,
            OAUTH_TOKEN_URL,
        )
        self._scopes = scopes or SCOPES_FULL

    @property
    def name(self) -> str:
        """What the person is choosing, if they are ever shown a choice."""
        return "Eleven Energy account"

    @property
    def extra_authorize_data(self) -> dict:
        """Add the scopes, and take a fresh verifier for each authorization.

        The base class generates one verifier when the implementation is created, and the
        implementation lives as long as Home Assistant does - so every authorization would share
        it, and a verifier that leaked once would unlock every future one. This is read once per
        authorize URL, so taking a new one here scopes it to the attempt that uses it.

        Two people setting this up on one Home Assistant at the same moment would have the second
        overwrite the first, and the first would fail at the exchange and need retrying. That is a
        better failure than a secret shared across every sign-in for the life of the process.
        """
        self.code_verifier = self.generate_code_verifier()

        data = {"scope": " ".join(self._scopes)}
        data.update(super().extra_authorize_data)
        return data


@callback
def async_register_implementation(hass: HomeAssistant) -> None:
    """Make the implementation available to the config flow.

    Registered during setup of the integration rather than of a config entry, because the flow
    needs it before any entry exists.
    """
    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, ElevenEnergyOAuth2Implementation(hass)
    )
