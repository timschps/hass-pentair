"""Config flow for the Pentair Intellipool integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    IntellipoolAuthError,
    IntellipoolClient,
    IntellipoolConnectionError,
    IntellipoolError,
)
from .const import CONF_API_KEY, CONF_INSTALL_ID, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)
CONF_SCAN_INTERVAL = "scan_interval"


def _user_schema(
    suggested_values: dict[str, Any] | None = None,
) -> vol.Schema:
    """Return the user step schema."""
    suggested_values = suggested_values or {}
    install_id = (
        vol.Required(CONF_INSTALL_ID, default=suggested_values[CONF_INSTALL_ID])
        if CONF_INSTALL_ID in suggested_values
        else vol.Required(CONF_INSTALL_ID)
    )
    return vol.Schema(
        {
            install_id: str,
            vol.Required(CONF_API_KEY): str,
        }
    )


def _options_schema(options: config_entries.ConfigEntry | dict[str, Any]) -> vol.Schema:
    """Return the options flow schema."""
    option_values = options.options if isinstance(options, config_entries.ConfigEntry) else options
    return vol.Schema(
        {
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=option_values.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=30)),
        }
    )


async def _validate_credentials(
    flow: config_entries.ConfigFlow,
    install_id: str,
    api_key: str,
) -> str | None:
    """Validate credentials and return an error reason if validation fails."""
    client = IntellipoolClient(
        async_get_clientsession(flow.hass),
        install_id,
        api_key,
    )

    try:
        await client.async_validate()
    except IntellipoolAuthError:
        return "invalid_auth"
    except IntellipoolConnectionError:
        return "cannot_connect"
    except IntellipoolError:
        return "unknown"
    except Exception:
        _LOGGER.exception("Unexpected exception while validating Intellipool credentials")
        return "unknown"
    return None


class IntellipoolConfigFlow(config_entries.ConfigFlow):
    """Handle a config flow for Pentair Intellipool."""

    VERSION = 1
    domain = DOMAIN  # Explicitly declare domain for HA versions expecting a class attribute.

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> IntellipoolOptionsFlow:
        """Create the options flow."""
        return IntellipoolOptionsFlow()

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial user step."""
        errors: dict[str, str] = {}
        suggested_values: dict[str, Any] = {}

        if user_input is not None:
            install_id = user_input[CONF_INSTALL_ID].strip()
            api_key = user_input[CONF_API_KEY].strip()
            suggested_values[CONF_INSTALL_ID] = install_id

            await self.async_set_unique_id(install_id)
            self._abort_if_unique_id_configured()

            if error := await _validate_credentials(self, install_id, api_key):
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=f"Pentair Intellipool {install_id}",
                    data={
                        CONF_INSTALL_ID: install_id,
                        CONF_API_KEY: api_key,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(suggested_values),
            errors=errors,
        )

    async def async_step_reauth(
        self,
        entry_data: dict[str, Any],
    ) -> config_entries.ConfigFlowResult:
        """Handle a reauthentication request."""
        await self.async_set_unique_id(entry_data[CONF_INSTALL_ID])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle the reauthentication confirmation step."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        install_id = entry.data[CONF_INSTALL_ID]

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            if error := await _validate_credentials(self, install_id, api_key):
                errors["base"] = error
            else:
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, CONF_API_KEY: api_key},
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    def _get_reauth_entry(self) -> config_entries.ConfigEntry:
        """Return the config entry being reauthenticated."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if entry is None:
            raise RuntimeError("Reauth entry not found")
        return entry


class IntellipoolOptionsFlow(config_entries.OptionsFlow):
    """Handle Pentair Intellipool options."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Manage the Intellipool options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(self.config_entry),
        )
