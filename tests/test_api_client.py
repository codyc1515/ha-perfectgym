"""Tests for transient PerfectGym API failures."""

import asyncio
import importlib.util
from pathlib import Path
import sys
from types import ModuleType
from unittest.mock import AsyncMock

import pytest

_ROOT = Path(__file__).parents[1] / "custom_components/perfectgym"


def _load_api_module():
    """Load the API client without requiring a Home Assistant installation."""
    if "aiohttp" not in sys.modules:
        aiohttp = ModuleType("aiohttp")

        class ClientError(Exception):
            pass

        aiohttp.ClientError = ClientError
        aiohttp.ClientResponse = object
        aiohttp.ClientSession = object
        sys.modules["aiohttp"] = aiohttp

    package = ModuleType("custom_components.perfectgym")
    package.__path__ = [str(_ROOT)]
    sys.modules["custom_components.perfectgym"] = package

    for name in ("models", "api"):
        module_name = f"custom_components.perfectgym.{name}"
        spec = importlib.util.spec_from_file_location(module_name, _ROOT / f"{name}.py")
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    return sys.modules["custom_components.perfectgym.api"]


class _Response:
    def __init__(self, status: int, token: str | None = None) -> None:
        self.status = status
        self.headers = {"jwt-token": token} if token else {}
        self.json_called = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def json(self, **kwargs):
        self.json_called = True
        raise AssertionError("A service-unavailable body must not be decoded as JSON")


class _Session:
    def __init__(self, responses: list[_Response]) -> None:
        self.responses = responses.copy()

    def post(self, *args, **kwargs) -> _Response:
        return self.responses.pop(0)


def test_login_retries_503_without_parsing_body(monkeypatch) -> None:
    api = _load_api_module()
    responses = [_Response(503), _Response(503), _Response(200, "token")]
    sleep = AsyncMock()
    monkeypatch.setattr(api.asyncio, "sleep", sleep)
    client = api.PerfectGymClient(
        _Session(responses), "https://example.test/", "u", "p"
    )

    asyncio.run(client.async_login())

    assert all(not response.json_called for response in responses)
    assert sleep.await_count == 2


def test_login_reports_terminal_503_as_temporary_outage(monkeypatch) -> None:
    api = _load_api_module()
    responses = [_Response(503), _Response(503), _Response(503)]
    sleep = AsyncMock()
    monkeypatch.setattr(api.asyncio, "sleep", sleep)
    client = api.PerfectGymClient(
        _Session(responses), "https://example.test/", "u", "p"
    )

    with pytest.raises(
        api.PerfectGymConnectionError,
        match=r"temporarily unavailable \(HTTP 503\)",
    ):
        asyncio.run(client.async_login())

    assert all(not response.json_called for response in responses)


def test_calendar_includes_recent_and_future_activity_pages() -> None:
    api = _load_api_module()
    recent_event = {
        "Id": 1,
        "Name": "Today",
        "StartTimeUtc": "2030-08-14T06:00:00Z",
        "Duration": "PT30M",
    }
    another_recent_event = {
        "Id": 2,
        "Name": "Earlier today",
        "StartTimeUtc": "2030-08-14T01:00:00Z",
        "Duration": "PT30M",
    }
    future_event = {
        "Id": 3,
        "Name": "Tomorrow",
        "StartTimeUtc": "2030-08-15T06:00:00Z",
        "Duration": "PT30M",
    }

    async def get(path, params=None):
        if path.endswith("GetCalendar"):
            return {
                "RecentItems": {
                    "Items": [recent_event],
                    "Page": 0,
                    "HasMore": True,
                },
                "FutureItems": {
                    "Items": [recent_event, future_event],
                    "Page": 0,
                    "HasMore": False,
                },
            }
        assert path.endswith("GetRecentActivities")
        assert params == {"page": 1}
        return {
            "Items": [another_recent_event],
            "Page": 1,
            "HasMore": False,
        }

    client = api.PerfectGymClient(
        _Session([]), "https://example.test/", "test-user", "test-password"
    )
    client._get = AsyncMock(side_effect=get)

    events = asyncio.run(client.async_get_events())

    assert [event.summary for event in events] == [
        "Earlier today",
        "Today",
        "Tomorrow",
    ]
