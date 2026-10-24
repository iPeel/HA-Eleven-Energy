"""Constants for the Eleven Energy integration."""

from homeassistant.const import Platform

DOMAIN = "eleven_energy"
PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]
BASE_URL = "https://portal.elevenenergy.co.uk/api/v1/"
POLL_INTERVAL_SECONDS = 60

# Signing in with an Eleven Energy account rather than pasting an API key.
#
# The client id is deliberately not a secret. This is a public OAuth client: it has no secret at
# all, because one shipped inside a published integration is public the moment it ships. What
# takes the secret's place is PKCE, which proves the application redeeming the code is the one
# that started the flow - and the server refuses this client without it.
OAUTH_CLIENT_ID = "home-assistant"
OAUTH_AUTHORIZE_URL = "https://integrate.elevenenergy.co.uk/oauth2/authorize"
OAUTH_TOKEN_URL = "https://integrate.elevenenergy.co.uk/oauth2/token"

# Asked for at the consent screen. Read-only leaves out control, so somebody who only wants
# graphs is not asked to hand over the battery.
SCOPES_READ_ONLY = ["site:read", "devices:read", "telemetry:read"]
SCOPES_FULL = [*SCOPES_READ_ONLY, "control:write"]
