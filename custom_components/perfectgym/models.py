"""Data models and normalization helpers for PerfectGym."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import re
from typing import Any

_DURATION_RE = re.compile(
    r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?"
    r"(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?)?$"
)


@dataclass(frozen=True, slots=True)
class PerfectGymEvent:
    """A normalized forthcoming PerfectGym booking."""

    uid: str
    summary: str
    start: datetime
    end: datetime
    location: str | None
    description: str | None


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_duration(value: str | None) -> timedelta | None:
    if not value or (match := _DURATION_RE.fullmatch(value)) is None:
        return None
    parts = match.groupdict(default="0")
    return timedelta(
        days=int(parts["days"]),
        hours=int(parts["hours"]),
        minutes=int(parts["minutes"]),
        seconds=float(parts["seconds"]),
    )


def _event_end(item: dict[str, Any], start: datetime) -> datetime:
    if (duration := _parse_duration(item.get("Duration"))) is not None:
        return start + duration
    try:
        local_start = datetime.fromisoformat(item["StartTime"])
        local_end = datetime.fromisoformat(item["EndTime"])
        if local_end <= local_start:
            local_end += timedelta(days=1)
        return start + (local_end - local_start)
    except (KeyError, TypeError, ValueError):
        return start + timedelta(hours=1)


def _people(item: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for user in item.get("Users") or []:
        name = " ".join(
            part.strip()
            for part in (user.get("FirstName") or "", user.get("LastName") or "")
            if part.strip()
        )
        if name and name not in names:
            names.append(name)
    return names


def normalize_event(item: dict[str, Any]) -> PerfectGymEvent:
    """Normalize one Client Portal calendar item."""
    start = _parse_utc(item["StartTimeUtc"])
    end = _event_end(item, start)
    location = " — ".join(
        value.strip()
        for value in (item.get("Club") or "", item.get("Zone") or "")
        if value.strip()
    ) or None

    details: list[str] = []
    if people := _people(item):
        details.append(f"Participants: {', '.join(people)}")
    if trainer := item.get("TrainerDisplayName"):
        details.append(f"Trainer: {trainer}")
    if item.get("IsStandBy"):
        standby = "Standby"
        if queue_number := item.get("StandByQueueNumber"):
            standby += f" (queue {queue_number})"
        details.append(standby)
    if item_type := item.get("Type"):
        details.append(f"Type: {item_type}")
    if booking_id := item.get("ClassBookingId"):
        details.append(f"Booking ID: {booking_id}")

    raw_uid = item.get("ClassBookingId") or item.get("Id")
    uid_value = raw_uid or f"{item.get('Name', 'event')}-{item['StartTimeUtc']}"
    return PerfectGymEvent(
        uid=f"perfect-gym-{uid_value}",
        summary=str(item.get("Name") or "PerfectGym booking"),
        start=start,
        end=end,
        location=location,
        description="\n".join(details) or None,
    )
