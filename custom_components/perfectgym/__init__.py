"""PerfectGym calendar integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import PerfectGymCoordinator

type PerfectGymConfigEntry = ConfigEntry[PerfectGymCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: PerfectGymConfigEntry) -> bool:
    """Set up PerfectGym from a config entry."""
    coordinator = PerfectGymCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PerfectGymConfigEntry) -> bool:
    """Unload a PerfectGym config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
