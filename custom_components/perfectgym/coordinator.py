"""Data coordinator for PerfectGym."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    PerfectGymAuthError,
    PerfectGymClient,
    PerfectGymConnectionError,
)
from .const import CONF_BASE_URL, DOMAIN, UPDATE_INTERVAL
from .models import PerfectGymEvent

_LOGGER = logging.getLogger(__name__)


class PerfectGymCoordinator(DataUpdateCoordinator[tuple[PerfectGymEvent, ...]]):
    """Fetch forthcoming PerfectGym activities."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            always_update=False,
        )
        self.client = PerfectGymClient(
            async_get_clientsession(hass),
            entry.data[CONF_BASE_URL],
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
        )

    async def _async_update_data(self) -> tuple[PerfectGymEvent, ...]:
        try:
            return await self.client.async_get_events()
        except PerfectGymAuthError as err:
            raise ConfigEntryAuthFailed from err
        except PerfectGymConnectionError as err:
            raise UpdateFailed(str(err)) from err
