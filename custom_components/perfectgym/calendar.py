"""Calendar platform for PerfectGym."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import PerfectGymConfigEntry
from .const import DEFAULT_NAME, DOMAIN
from .coordinator import PerfectGymCoordinator
from .models import PerfectGymEvent


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PerfectGymConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the PerfectGym calendar entity."""
    async_add_entities([PerfectGymCalendar(entry.runtime_data, entry)])


def _as_calendar_event(event: PerfectGymEvent) -> CalendarEvent:
    return CalendarEvent(
        start=event.start,
        end=event.end,
        summary=event.summary,
        description=event.description,
        location=event.location,
        uid=event.uid,
    )


class PerfectGymCalendar(CoordinatorEntity[PerfectGymCoordinator], CalendarEntity):
    """Read-only calendar containing forthcoming PerfectGym bookings."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self, coordinator: PerfectGymCoordinator, entry: PerfectGymConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title or DEFAULT_NAME,
            "manufacturer": "PerfectGym",
            "configuration_url": coordinator.client.base_url,
            "entry_type": DeviceEntryType.SERVICE,
        }

    @property
    def event(self) -> CalendarEvent | None:
        """Return the active event, or the next forthcoming event."""
        now = dt_util.now()
        events = self.coordinator.data or ()
        active = next((item for item in events if item.start <= now < item.end), None)
        upcoming = active or next((item for item in events if item.start > now), None)
        return _as_calendar_event(upcoming) if upcoming else None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return events overlapping the requested half-open time range."""
        return [
            _as_calendar_event(item)
            for item in (self.coordinator.data or ())
            if item.end > start_date and item.start < end_date
        ]
