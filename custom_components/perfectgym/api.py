"""Async client for the PerfectGym Client Portal 2 API."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import urljoin

from aiohttp import ClientError, ClientResponse, ClientSession

from .models import PerfectGymEvent, normalize_event

_AUTH_FAILURE_STATUSES = {401, 403, 498, 499}
_MAX_ACTIVITY_PAGES = 100
_RETRYABLE_STATUSES = {429, 502, 503, 504}
_TRANSIENT_ATTEMPTS = 3

_LOGGER = logging.getLogger(__name__)


class PerfectGymError(Exception):
    """Base PerfectGym client error."""


class PerfectGymAuthError(PerfectGymError):
    """PerfectGym rejected the credentials or session."""


class PerfectGymConnectionError(PerfectGymError):
    """PerfectGym could not be reached."""


class PerfectGymClient:
    """Client for the private web API used by PerfectGym Client Portal 2."""

    def __init__(
        self,
        session: ClientSession,
        base_url: str,
        login: str,
        password: str,
    ) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/") + "/"
        self._login = login
        self._password = password
        self._token: str | None = None

    @property
    def base_url(self) -> str:
        """Return the normalized portal base URL."""
        return self._base_url

    def _url(self, path: str) -> str:
        return urljoin(self._base_url, path)

    @property
    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json, text/plain, */*",
            "CP-LANG": "en",
            "CP-MODE": "desktop",
            "Referer": self._base_url,
            "X-Hash": "#/MyCalendar",
            "X-Requested-With": "XMLHttpRequest",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def async_login(self) -> None:
        """Authenticate and retain the JWT returned in the response headers."""
        payload = {
            "Login": self._login,
            "Password": self._password,
            "RememberMe": True,
        }
        headers = self._headers
        headers["X-Hash"] = "#/Login"

        for attempt in range(_TRANSIENT_ATTEMPTS):
            try:
                async with self._session.post(
                    self._url("Auth/Login"), headers=headers, json=payload
                ) as response:
                    if response.status in _RETRYABLE_STATUSES:
                        if attempt < _TRANSIENT_ATTEMPTS - 1:
                            await _retry_wait(attempt, response.status)
                            continue
                        raise PerfectGymConnectionError(
                            _http_error_message("login", response.status)
                        )
                    if response.status in _AUTH_FAILURE_STATUSES:
                        data = await self._json(response)
                        raise PerfectGymAuthError(_error_message(data))
                    if response.status >= 400:
                        raise PerfectGymConnectionError(
                            _http_error_message("login", response.status)
                        )
                    token = response.headers.get("jwt-token")
                    if not token:
                        raise PerfectGymAuthError(
                            "PerfectGym login did not return an authentication token"
                        )
                    self._token = token
                    return
            except PerfectGymError:
                raise
            except (ClientError, TimeoutError) as err:
                if attempt < _TRANSIENT_ATTEMPTS - 1:
                    await _retry_wait(attempt)
                    continue
                raise PerfectGymConnectionError(
                    "Unable to connect to the PerfectGym service"
                ) from err

    async def _json(self, response: ClientResponse) -> Any:
        try:
            return await response.json(content_type=None)
        except (ValueError, TypeError) as err:
            raise PerfectGymConnectionError(
                f"PerfectGym returned an invalid response (HTTP {response.status})"
            ) from err

    async def _get(self, path: str, params: dict[str, int] | None = None) -> Any:
        """GET JSON, automatically logging in and retrying an expired session once."""
        if self._token is None:
            await self.async_login()

        transient_attempt = 0
        auth_retried = False
        while True:
            try:
                async with self._session.get(
                    self._url(path), headers=self._headers, params=params
                ) as response:
                    if response.status in {401, 403, 498} and not auth_retried:
                        self._token = None
                        await self.async_login()
                        auth_retried = True
                        continue
                    if response.status in _RETRYABLE_STATUSES:
                        if transient_attempt < _TRANSIENT_ATTEMPTS - 1:
                            await _retry_wait(transient_attempt, response.status)
                            transient_attempt += 1
                            continue
                        raise PerfectGymConnectionError(
                            _http_error_message("request", response.status)
                        )
                    if response.status in _AUTH_FAILURE_STATUSES:
                        data = await self._json(response)
                        raise PerfectGymAuthError(_error_message(data))
                    if response.status >= 400:
                        raise PerfectGymConnectionError(
                            _http_error_message("request", response.status)
                        )
                    return await self._json(response)
            except PerfectGymError:
                raise
            except (ClientError, TimeoutError) as err:
                if transient_attempt < _TRANSIENT_ATTEMPTS - 1:
                    await _retry_wait(transient_attempt)
                    transient_attempt += 1
                    continue
                raise PerfectGymConnectionError(
                    "Unable to connect to the PerfectGym service"
                ) from err

    async def async_get_events(self) -> tuple[PerfectGymEvent, ...]:
        """Return recent and forthcoming activities from every page."""
        calendar = await self._get("MyCalendar/MyCalendar/GetCalendar")
        items = await self._async_collect_activity_pages(
            calendar.get("RecentItems") or {},
            "MyCalendar/MyCalendar/GetRecentActivities",
        )
        items.extend(
            await self._async_collect_activity_pages(
                calendar.get("FutureItems") or {},
                "MyCalendar/MyCalendar/GetFutureActivities",
            )
        )

        merged: dict[tuple[Any, Any], dict[str, Any]] = {}
        for item in items:
            key = (
                item.get("Id") or item.get("ClassBookingId") or item.get("Name"),
                item.get("StartTimeUtc"),
            )
            if key in merged:
                existing_users = merged[key].setdefault("Users", [])
                known_ids = {user.get("Id") for user in existing_users}
                existing_users.extend(
                    user
                    for user in item.get("Users") or []
                    if user.get("Id") not in known_ids
                )
            else:
                merged[key] = dict(item)

        events: list[PerfectGymEvent] = []
        for item in merged.values():
            try:
                events.append(normalize_event(item))
            except (KeyError, TypeError, ValueError):
                continue
        return tuple(sorted(events, key=lambda event: (event.start, event.end)))

    async def _async_collect_activity_pages(
        self, first_page: dict[str, Any], path: str
    ) -> list[dict[str, Any]]:
        """Collect an initial activity page and all of its remaining pages."""
        items = list(first_page.get("Items") or [])
        page = int(first_page.get("Page") or 0)
        has_more = bool(first_page.get("HasMore"))

        for _ in range(_MAX_ACTIVITY_PAGES):
            if not has_more:
                return items
            result = await self._get(path, params={"page": page + 1})
            page = int(result.get("Page", page + 1))
            has_more = bool(result.get("HasMore"))
            items.extend(result.get("Items") or [])

        if has_more:
            raise PerfectGymConnectionError(
                "PerfectGym returned more calendar pages than the safety limit"
            )
        return items


def _error_message(data: Any) -> str:
    """Extract a useful error without logging credentials or tokens."""
    if isinstance(data, dict):
        errors = data.get("Errors")
        if isinstance(errors, list) and errors and isinstance(errors[0], dict):
            if message := errors[0].get("Message"):
                return str(message)
    return "PerfectGym authentication failed"


def _http_error_message(operation: str, status: int) -> str:
    """Return a clear error for an HTTP failure without exposing response data."""
    if status in _RETRYABLE_STATUSES:
        return f"PerfectGym service temporarily unavailable (HTTP {status})"
    return f"PerfectGym {operation} returned HTTP {status}"


async def _retry_wait(attempt: int, status: int | None = None) -> None:
    """Wait briefly before retrying a transient service or network failure."""
    delay = 2**attempt
    if status is None:
        _LOGGER.debug("PerfectGym connection failed; retrying in %s seconds", delay)
    else:
        _LOGGER.debug(
            "PerfectGym returned HTTP %s; retrying in %s seconds", status, delay
        )
    await asyncio.sleep(delay)
