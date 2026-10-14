"""Sensor platform for the Pentair Intellipool integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DATETIME_TYPE_INFO,
    IntellipoolProbeDescription,
    get_probe_description,
    type_info_name,
    type_info_slug,
)
from .coordinator import IntellipoolDataUpdateCoordinator

KIND_DATETIME = "datetime"
KIND_NUMERIC = "numeric"
KIND_UNKNOWN = "unknown"
SENSOR_KINDS = frozenset({KIND_NUMERIC, KIND_DATETIME, KIND_UNKNOWN})

_MISSING = object()
_FALLBACK_VALUE_KEYS = ("native_value", "value")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[IntellipoolDataUpdateCoordinator],
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Intellipool sensors from the probes returned by the coordinator."""
    coordinator = entry.runtime_data
    data = coordinator.data or {}
    async_add_entities(
        IntellipoolSensor(coordinator, type_info)
        for type_info, record in data.items()
        if _record_kind(record) in SENSOR_KINDS
    )


class IntellipoolSensor(
    CoordinatorEntity[IntellipoolDataUpdateCoordinator],
    SensorEntity,
):
    """Representation of a Pentair Intellipool probe sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IntellipoolDataUpdateCoordinator,
        type_info: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._type_info = type_info
        self.entity_description = _sensor_description(type_info)
        self._attr_unique_id = f"{coordinator.install_id}_{type_info}"
        self._attr_device_info = coordinator.device_info
        if self._kind == KIND_DATETIME:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> Any:
        """Return the sensor value from the current probe payload."""
        value = self._probe_value
        if value is _MISSING:
            return None
        return value

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the payload unit, falling back to known probe metadata."""
        if self._is_datetime:
            return None

        payload_unit = self._probe_unit
        if payload_unit:
            return _normalize_temperature_unit(payload_unit)
        return self.entity_description.native_unit_of_measurement

    @property
    def device_class(self) -> SensorDeviceClass | str | None:
        """Return the sensor device class."""
        if self._is_datetime:
            return SensorDeviceClass.TIMESTAMP
        return self.entity_description.device_class

    @property
    def state_class(self) -> SensorStateClass | str | None:
        """Return a measurement state class for numeric probe values."""
        if self._is_datetime:
            return None

        kind = self._kind
        if kind == KIND_NUMERIC:
            return SensorStateClass.MEASUREMENT
        if kind == KIND_UNKNOWN:
            value = self._probe_value
            if isinstance(value, int | float) and not isinstance(value, bool):
                return SensorStateClass.MEASUREMENT
            return None
        return self.entity_description.state_class

    @property
    def available(self) -> bool:
        """Return whether the entity has current data."""
        value = self._probe_value
        return super().available and value is not _MISSING and value is not None

    @property
    def _kind(self) -> str | None:
        """Return the current record kind."""
        return _record_kind(self._record)

    @property
    def _is_datetime(self) -> bool:
        """Return whether this entity represents the measurement timestamp."""
        return self._type_info == DATETIME_TYPE_INFO or self._kind == KIND_DATETIME

    @property
    def _record(self) -> Any:
        """Return the current probe record."""
        data = self.coordinator.data or {}
        return data.get(self._type_info, _MISSING)

    @property
    def _probe_value(self) -> Any:
        """Extract the native value from scalar or normalized probe payloads."""
        record = self._record
        if record is _MISSING or record is None:
            return _MISSING
        if not isinstance(record, Mapping):
            return record

        for key in _FALLBACK_VALUE_KEYS:
            if key in record:
                return record[key]
        return _MISSING

    @property
    def _probe_unit(self) -> str | None:
        """Return the payload unit for this probe, if any."""
        record = self._record
        if not isinstance(record, Mapping):
            return None
        unit = record.get("unit")
        return str(unit) if unit not in (None, "") else None


def _sensor_description(type_info: str) -> IntellipoolProbeDescription:
    """Return known metadata or a generic description for an API typeInfo."""
    description = get_probe_description(type_info)
    if description.name is not None:
        return description
    return IntellipoolProbeDescription(
        type_info=type_info,
        key=type_info_slug(type_info),
        name=type_info_name(type_info),
    )


def _record_kind(record: Any) -> str | None:
    """Return the normalized record kind."""
    if not isinstance(record, Mapping) or "kind" not in record:
        return None
    kind = record["kind"]
    return kind if isinstance(kind, str) else None


def _normalize_temperature_unit(unit: str) -> str:
    """Normalize API temperature symbols to Home Assistant constants."""
    if unit == "°C":
        return UnitOfTemperature.CELSIUS
    if unit == "°F":
        return UnitOfTemperature.FAHRENHEIT
    return unit
