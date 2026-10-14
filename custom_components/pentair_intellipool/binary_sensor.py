"""Binary sensor platform for the Pentair Intellipool integration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BINARY_FLAGS, type_info_name, type_info_slug
from .coordinator import IntellipoolDataUpdateCoordinator

KIND_BINARY = "binary"

_MISSING = object()


@dataclass(frozen=True, kw_only=True)
class IntellipoolBinarySensorDescription(BinarySensorEntityDescription):
    """Description for an Intellipool binary probe."""

    type_info: str


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[IntellipoolDataUpdateCoordinator],
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Intellipool binary sensors from boolean probes."""
    coordinator = entry.runtime_data
    data = coordinator.data or {}
    async_add_entities(
        IntellipoolBinarySensor(coordinator, type_info)
        for type_info, record in data.items()
        if _is_binary_record(record)
    )


class IntellipoolBinarySensor(
    CoordinatorEntity[IntellipoolDataUpdateCoordinator],
    BinarySensorEntity,
):
    """Representation of an Intellipool binary probe."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IntellipoolDataUpdateCoordinator,
        type_info: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._type_info = type_info
        self.entity_description = IntellipoolBinarySensorDescription(
            type_info=type_info,
            key=type_info_slug(type_info),
            name=BINARY_FLAGS.get(type_info, type_info_name(type_info)),
            device_class=_device_class(type_info),
        )
        self._attr_unique_id = f"{coordinator.install_id}_{type_info}"
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool | None:
        """Return whether the binary probe is active."""
        value = self._native_value
        if value is _MISSING or value is None:
            return None
        return bool(value)

    @property
    def available(self) -> bool:
        """Return whether the entity has current data."""
        value = self._native_value
        return super().available and value is not _MISSING and value is not None

    @property
    def _record(self) -> Any:
        """Return the current probe record."""
        data = self.coordinator.data or {}
        return data.get(self._type_info, _MISSING)

    @property
    def _native_value(self) -> Any:
        """Return the current native boolean value."""
        record = self._record
        if record is _MISSING or record is None:
            return _MISSING
        if not isinstance(record, Mapping):
            return record
        if "native_value" in record:
            return record["native_value"]
        if "value" in record:
            return _coerce_bool(record["value"])
        return _MISSING


def _is_binary_record(record: Any) -> bool:
    """Return whether a probe record should be represented as a binary sensor."""
    if not isinstance(record, Mapping) or "kind" not in record:
        return False
    return record["kind"] == KIND_BINARY


def _device_class(type_info: str) -> BinarySensorDeviceClass | None:
    """Return a device class for known Intellipool boolean flags."""
    if "LIGHTING" in type_info:
        return BinarySensorDeviceClass.LIGHT
    if any(token in type_info for token in ("FILTRATION", "HEATING", "PUMP")):
        return BinarySensorDeviceClass.RUNNING
    return None


def _coerce_bool(value: Any) -> bool | Any:
    """Coerce API boolean strings when legacy payloads are encountered."""
    if isinstance(value, str):
        lowered = value.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
    return value
