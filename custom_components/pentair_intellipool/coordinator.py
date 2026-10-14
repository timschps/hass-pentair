"""Data update coordinator for the Pentair Intellipool integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    IntellipoolAuthError,
    IntellipoolClient,
    IntellipoolConnectionError,
    IntellipoolError,
)
from .const import CONF_INSTALL_ID, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)
CONF_SCAN_INTERVAL = "scan_interval"


class IntellipoolDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that refreshes Intellipool probe data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: IntellipoolClient,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self.install_id = entry.data[CONF_INSTALL_ID]
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device registry info for this Intellipool installation."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.install_id)},
            manufacturer="Pentair",
            model="Intellipool",
            name="Pentair Intellipool",
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch fresh probe data from Intellipool."""
        try:
            return await self.client.async_get_all_probes()
        except IntellipoolAuthError as err:
            raise ConfigEntryAuthFailed("Intellipool authentication failed") from err
        except (IntellipoolConnectionError, IntellipoolError) as err:
            raise UpdateFailed("Unable to update Intellipool data") from err
