"""Constants for the PerfectGym integration."""

from datetime import timedelta

DOMAIN = "perfectgym"
PLATFORMS = ["calendar"]

CONF_BASE_URL = "base_url"
DEFAULT_BASE_URL = "https://recandsport.perfectgym.com.au/ClientPortal2/"
DEFAULT_NAME = "PerfectGym"

UPDATE_INTERVAL = timedelta(days=1)
