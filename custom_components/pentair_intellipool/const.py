"""Constants for the Pentair Intellipool integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    Platform,
    UnitOfElectricPotential,
    UnitOfTemperature,
)

DOMAIN = "pentair_intellipool"

CONF_INSTALL_ID = "install_id"
CONF_API_KEY = "api_key"

DEFAULT_SCAN_INTERVAL = 60

API_BASE_URL = "https://api.domotique-piscine.eu/api"

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

DATETIME_TYPE_INFO = "DATETIME"  # Parsed by the API client as a timestamp sensor value.


@dataclass(frozen=True, kw_only=True)
class IntellipoolProbeDescription(SensorEntityDescription):
    """Description for an Intellipool probe sensor."""

    type_info: str


KNOWN_SENSOR_TYPES: dict[str, IntellipoolProbeDescription] = {
    "WATER_TEMP": IntellipoolProbeDescription(
        type_info="WATER_TEMP",
        key="water_temp",
        name="Water temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "AIR_TEMP": IntellipoolProbeDescription(
        type_info="AIR_TEMP",
        key="air_temp",
        name="Air temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "ORP": IntellipoolProbeDescription(
        type_info="ORP",
        key="orp",
        name="ORP",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "PH": IntellipoolProbeDescription(
        type_info="PH",
        key="ph",
        name="pH",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "CONDUCTIVITY": IntellipoolProbeDescription(
        type_info="CONDUCTIVITY",
        key="conductivity",
        name="Conductivity",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "UV": IntellipoolProbeDescription(
        type_info="UV",
        key="uv",
        name="UV",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "CHLORINE_FREE": IntellipoolProbeDescription(
        type_info="CHLORINE_FREE",
        key="chlorine_free",
        name="Free chlorine",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "CHLORINE_ACTIVE": IntellipoolProbeDescription(
        type_info="CHLORINE_ACTIVE",
        key="chlorine_active",
        name="Active chlorine",
        state_class=SensorStateClass.MEASUREMENT,
    ),
}

BINARY_FLAGS: dict[str, str] = {
    "OMEOTECH_FLAG_HEATING": "Heating",
    "OMEOTECH_FLAG_FILTRATION": "Filtration",
    "OMEOTECH_FLAG_LIGHTING": "Lighting",
    "OMEOTECH_FLAG_AUX1": "Aux 1",
}

PROBE_SENSOR_DESCRIPTIONS = KNOWN_SENSOR_TYPES
PROBE_TYPE_INFOS: tuple[str, ...] = tuple(KNOWN_SENSOR_TYPES)


def type_info_slug(type_info: str) -> str:
    """Return a valid entity key slug for an API typeInfo."""
    return type_info.lower().replace("-", "_")


def type_info_name(type_info: str) -> str:
    """Return a sensible display name for a typeInfo."""
    if type_info == DATETIME_TYPE_INFO:
        return "Measurement time"
    if type_info in BINARY_FLAGS:
        return BINARY_FLAGS[type_info]
    return type_info.replace("_", " ").title()


def get_probe_description(type_info: str) -> IntellipoolProbeDescription:
    """Return known metadata or a generic measurement sensor description."""
    if type_info in KNOWN_SENSOR_TYPES:
        return KNOWN_SENSOR_TYPES[type_info]
    return IntellipoolProbeDescription(
        type_info=type_info,
        key=type_info_slug(type_info),
        name=type_info_name(type_info),
        state_class=SensorStateClass.MEASUREMENT,
    )
