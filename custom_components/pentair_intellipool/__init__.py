"""Pentair Intellipool integration for Home Assistant."""

from __future__ import annotations

from typing import TypeAlias

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import IntellipoolClient
from .const import CONF_API_KEY, CONF_INSTALL_ID, PLATFORMS
from .coordinator import IntellipoolDataUpdateCoordinator

IntellipoolConfigEntry: TypeAlias = ConfigEntry[IntellipoolDataUpdateCoordinator]


async def _async_update_listener(
    hass: HomeAssistant,
    entry: IntellipoolConfigEntry,
) -> None:
    """Reload the entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntellipoolConfigEntry,
) -> bool:
    """Set up Pentair Intellipool from a config entry."""
    client = IntellipoolClient(
        async_get_clientsession(hass),
        entry.data[CONF_INSTALL_ID],
        entry.data[CONF_API_KEY],
    )
    coordinator = IntellipoolDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: IntellipoolConfigEntry,
) -> bool:
    """Unload a Pentair Intellipool config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )
    if unload_ok:
        entry.runtime_data = None
    return unload_ok
