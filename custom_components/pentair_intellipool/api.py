"""Async client for the Pentair Intellipool API."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any
from urllib.parse import quote

import aiohttp
from homeassistant.util import dt as dt_util
from yarl import URL

from .const import API_BASE_URL, BINARY_FLAGS, DATETIME_TYPE_INFO, KNOWN_SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)
JSON_FORMAT = "json"
UNIT_KEYS = ("unit", "units", "unit_of_measurement")
DATETIME_FORMAT = "%d/%m/%Y %H:%M"
KIND_NUMERIC = "numeric"
KIND_BINARY = "binary"
KIND_DATETIME = "datetime"
KIND_UNKNOWN = "unknown"

ProbeReading = dict[str, Any]


class IntellipoolError(Exception):
    """Base exception for Intellipool client errors."""


class IntellipoolAuthError(IntellipoolError):
    """Raised when Intellipool rejects the configured credentials."""


class IntellipoolConnectionError(IntellipoolError):
    """Raised when Intellipool cannot be reached or returns invalid data."""


class IntellipoolClient:
    """Async client for the Intellipool probe API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        install_id: str,
        api_key: str,
    ) -> None:
        """Initialize the client.

        Args:
            session: Home Assistant managed aiohttp client session.
            install_id: Intellipool installation id from the portal.
            api_key: Intellipool API key from the portal. Never log this value.
        """
        self._session = session
        self._install_id = install_id
        self._api_key = api_key

    def _probe_url(self, type_info: str) -> URL:
        """Build the documented probe URL without embedding the API key."""
        install_id = quote(self._install_id, safe="")
        type_info = quote(type_info, safe="")
        return URL(f"{API_BASE_URL}/install/{install_id}/probe/{type_info}")

    def _probes_url(self) -> URL:
        """Build the documented bulk probes URL without embedding the API key."""
        install_id = quote(self._install_id, safe="")
        return URL(f"{API_BASE_URL}/install/{install_id}/probes")

    async def async_get_probe(
        self, type_info: str, fmt: str | None = None
    ) -> ProbeReading:
        """Fetch and normalize a single probe payload.

        Builds requests matching:
        ``/install/{installId}/probe/{typeInfo}?key={key}[&format={format}]``.
        ``format=json`` is requested by default because the official API defaults
        to text. The single-probe path uses lowercase-hyphen ``typeInfo`` values,
        while the bulk response uses uppercase-underscore keys.
        """
        effective_fmt = fmt or JSON_FORMAT
        params = {"key": self._api_key, "format": effective_fmt}

        try:
            async with self._session.get(
                self._probe_url(type_info),
                params=params,
                timeout=REQUEST_TIMEOUT,
            ) as response:
                body = await response.text()
                self._raise_for_status(response.status, body)
                payload = _decode_payload(body, response.content_type, effective_fmt)
                return parse_probe_payload(
                    payload, type_info=_canonical_bulk_type_info(type_info)
                )
        except IntellipoolError:
            raise
        except (aiohttp.ClientError, TimeoutError) as err:
            raise IntellipoolConnectionError("Unable to connect to Intellipool") from err

    async def async_get_probes(self) -> dict[str, ProbeReading]:
        """Fetch and normalize all probes from the preferred bulk endpoint."""
        params = {"key": self._api_key, "format": JSON_FORMAT}

        try:
            async with self._session.get(
                self._probes_url(),
                params=params,
                timeout=REQUEST_TIMEOUT,
            ) as response:
                body = await response.text()
                self._raise_for_status(response.status, body)
                payload = _decode_payload(body, response.content_type, JSON_FORMAT)
                return parse_probes_payload(payload)
        except IntellipoolError:
            raise
        except (aiohttp.ClientError, TimeoutError) as err:
            raise IntellipoolConnectionError("Unable to connect to Intellipool") from err

    def _raise_for_status(self, status: int, body: str) -> None:
        """Raise typed errors without exposing credentials."""
        if status in (401, 403) or _body_looks_like_auth_error(body):
            raise IntellipoolAuthError("Intellipool authentication failed")
        if status >= 400:
            raise IntellipoolConnectionError(
                f"Intellipool request failed with HTTP {status}"
            )

    async def async_get_all_probes(self) -> dict[str, ProbeReading]:
        """Fetch configured probe readings keyed by ``typeInfo``.

        The official bulk endpoint is the primary path. Authentication failures
        invalidate the client, while transport and unparseable payload failures
        surface as connection errors.
        """
        return await self.async_get_probes()

    async def async_validate(self) -> bool:
        """Validate credentials by confirming at least one bulk probe parses."""
        data = await self.async_get_probes()
        return bool(data)


def parse_probes_payload(payload: Any) -> dict[str, ProbeReading]:
    """Normalize the confirmed ``{"values": [...]}`` bulk probes payload."""
    if not isinstance(payload, Mapping) or not isinstance(payload.get("values"), list):
        raise IntellipoolConnectionError("Intellipool bulk response has no values list")

    data: dict[str, ProbeReading] = {}
    for item in payload["values"]:
        if not isinstance(item, Mapping):
            continue
        type_info = item.get("typeInfo")
        if not isinstance(type_info, str) or not type_info:
            continue
        _add_probe_reading(data, type_info, item)
    return data


def _add_probe_reading(
    data: dict[str, ProbeReading], type_info: str, payload: Any
) -> None:
    """Add a parsed probe reading, skipping individual malformed entries."""
    try:
        data[type_info] = parse_probe_payload(payload)
    except IntellipoolConnectionError as err:
        _LOGGER.debug(
            "Skipping Intellipool probe %s after failed parse: %s",
            type_info,
            err,
        )


def _decode_payload(body: str, content_type: str, fmt: str | None) -> Any:
    """Decode JSON when advertised or requested; otherwise keep text."""
    text = body.strip()
    if not text:
        raise IntellipoolConnectionError("Intellipool returned an empty response")

    wants_json = fmt == JSON_FORMAT or content_type == "application/json"
    looks_json = text[:1] in ("{", "[")
    if wants_json or looks_json:
        try:
            return json.loads(text)
        except json.JSONDecodeError as err:
            if wants_json or looks_json:
                raise IntellipoolConnectionError(
                    "Intellipool returned malformed JSON"
                ) from err
    return text


def parse_probe_payload(payload: Any, *, type_info: str | None = None) -> ProbeReading:
    """Normalize a probe payload to the confirmed record shape."""
    if isinstance(payload, list) and len(payload) == 1:
        return parse_probe_payload(payload[0], type_info=type_info)

    if isinstance(payload, Mapping):
        payload_type_info = payload.get("typeInfo")
        effective_type_info = (
            payload_type_info if isinstance(payload_type_info, str) else type_info
        )
        if "value" not in payload:
            raise IntellipoolConnectionError("Intellipool response has no probe value")
        raw_value = payload["value"]
        unit = _extract_unit(payload)
        return _normalize_probe_value(raw_value, effective_type_info, unit)

    if payload is None:
        raise IntellipoolConnectionError("Intellipool response has no probe value")
    return _normalize_probe_value(payload, type_info, None)


def _normalize_probe_value(
    raw_value: Any, type_info: str | None, unit: str | None
) -> ProbeReading:
    """Return a normalized probe record."""
    raw = raw_value if isinstance(raw_value, str) else str(raw_value)
    value = raw
    native_value, kind = _parse_native_value(raw, type_info)
    return {
        "raw": raw,
        "value": value,
        "native_value": native_value,
        "unit": unit,
        "kind": kind,
    }


def _parse_native_value(raw: str, type_info: str | None) -> tuple[Any, str]:
    """Parse a raw API string into a native value and kind."""
    text = raw.strip()
    canonical_type_info = _canonical_bulk_type_info(type_info) if type_info else None
    lower_text = text.lower()

    if canonical_type_info == DATETIME_TYPE_INFO:
        try:
            parsed = datetime.strptime(text, DATETIME_FORMAT).replace(
                tzinfo=dt_util.DEFAULT_TIME_ZONE
            )
        except ValueError:
            return raw, KIND_UNKNOWN
        return dt_util.as_local(parsed), KIND_DATETIME

    if (
        canonical_type_info in BINARY_FLAGS
        or (canonical_type_info or "").startswith("OMEOTECH_FLAG_")
        or lower_text in ("true", "false")
    ):
        if lower_text == "true":
            return True, KIND_BINARY
        if lower_text == "false":
            return False, KIND_BINARY
        return raw, KIND_UNKNOWN

    if canonical_type_info in KNOWN_SENSOR_TYPES or canonical_type_info is None:
        parsed = _parse_float(text)
        if parsed is not None:
            return parsed, KIND_NUMERIC
        if canonical_type_info in KNOWN_SENSOR_TYPES:
            return raw, KIND_UNKNOWN

    parsed = _parse_float(text)
    if parsed is not None:
        return parsed, KIND_NUMERIC
    return raw, KIND_UNKNOWN


def _parse_float(text: str) -> float | None:
    """Parse an API numeric string, accepting a leading plus sign."""
    try:
        return float(text.removeprefix("+"))
    except ValueError:
        return None


def _extract_unit(source: Mapping[str, Any]) -> str | None:
    """Return the first non-empty unit value."""
    for key in UNIT_KEYS:
        value = source.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _canonical_bulk_type_info(type_info: str | None) -> str | None:
    """Convert single-probe names to the bulk response casing."""
    if type_info is None:
        return None
    return type_info.replace("-", "_").upper()


def _body_looks_like_auth_error(body: str) -> bool:
    """Detect textual or JSON auth failures returned with a non-auth status."""
    text = body.lower()
    return any(
        marker in text
        for marker in (
            "unauthorized",
            "forbidden",
            "invalid key",
            "invalid api",
            "authentication failed",
            "invalid credentials",
        )
    )
