"""Constants for the Eleven Energy integration."""

from homeassistant.const import Platform

DOMAIN = "eleven_energy"
PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]
BASE_URL = "https://portal.elevenenergy.co.uk/api/v1/"
POLL_INTERVAL_SECONDS = 60
