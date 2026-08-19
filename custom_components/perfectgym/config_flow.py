"""Config flow for PerfectGym."""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PerfectGymAuthError, PerfectGymClient, PerfectGymConnectionError
from .const import CONF_BASE_URL, DEFAULT_BASE_URL, DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_BASE_URL, default=defaults.get(CONF_BASE_URL, DEFAULT_BASE_URL)
            ): str,
            vol.Required(CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")): str,
            vol.Required(CONF_PASSWORD): str,
        }
    )


class PerfectGymConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a PerfectGym config flow."""

    VERSION = 1

    async def _validate(self, data: dict[str, Any]) -> str:
        client = PerfectGymClient(
            async_get_clientsession(self.hass),
            data[CONF_BASE_URL],
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
        )
        await client.async_get_events()
        return client.base_url

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle setup initiated by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                user_input[CONF_BASE_URL] = await self._validate(user_input)
            except PerfectGymAuthError:
                errors["base"] = "invalid_auth"
            except PerfectGymConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001 - config flows must remain recoverable
                _LOGGER.exception("Unexpected error while connecting to PerfectGym")
                errors["base"] = "unknown"
            else:
                identity = (
                    f"{user_input[CONF_BASE_URL]}|"
                    f"{user_input[CONF_USERNAME].casefold()}"
                )
                await self.async_set_unique_id(sha256(identity.encode()).hexdigest())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=DEFAULT_NAME, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication after credentials stop working."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate replacement credentials."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            updated = {**entry.data, **user_input}
            try:
                await self._validate(updated)
            except PerfectGymAuthError:
                errors["base"] = "invalid_auth"
            except PerfectGymConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error while reconnecting PerfectGym")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(entry, data=updated)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=entry.data[CONF_USERNAME]
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
