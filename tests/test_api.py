"""Tests for PerfectGym event normalization."""

from datetime import UTC, datetime
import importlib.util
from pathlib import Path
import sys

_SPEC = importlib.util.spec_from_file_location(
    "perfectgym_models",
    Path(__file__).parents[1] / "custom_components/perfectgym/models.py",
)
assert _SPEC and _SPEC.loader
_MODELS = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODELS
_SPEC.loader.exec_module(_MODELS)
normalize_event = _MODELS.normalize_event


def test_normalize_group_class() -> None:
    event = normalize_event(
        {
            "Id": 1001,
            "Type": "GroupClass",
            "Name": "Example Class",
            "StartTime": "2030-08-14T18:15:00",
            "StartTimeUtc": "2030-08-14T06:15:00Z",
            "EndTime": "2030-08-14T18:40:00",
            "Duration": "PT25M",
            "Users": [{"Id": 12345, "FirstName": "Example", "LastName": "Member"}],
            "Club": "Example Recreation Centre",
            "Zone": "Studio 1",
            "ClassBookingId": 2001,
            "IsStandBy": False,
            "TrainerDisplayName": "Example Trainer",
        }
    )

    assert event.uid == "perfect-gym-2001"
    assert event.summary == "Example Class"
    assert event.start == datetime(2030, 8, 14, 6, 15, tzinfo=UTC)
    assert event.end == datetime(2030, 8, 14, 6, 40, tzinfo=UTC)
    assert event.location == "Example Recreation Centre — Studio 1"
    assert "Participants: Example Member" in event.description
    assert "Trainer: Example Trainer" in event.description


def test_normalize_falls_back_to_local_wall_clock_duration() -> None:
    event = normalize_event(
        {
            "Id": 1,
            "Name": "Late class",
            "StartTime": "2030-08-14T23:45:00",
            "StartTimeUtc": "2030-08-14T11:45:00Z",
            "EndTime": "2030-08-15T00:15:00",
        }
    )

    assert event.end == datetime(2030, 8, 14, 12, 15, tzinfo=UTC)
