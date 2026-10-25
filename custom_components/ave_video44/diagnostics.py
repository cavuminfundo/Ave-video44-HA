"""Diagnostics support for AVE Video V44 integration."""

from typing import Any, Dict, Set

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

try:
    from homeassistant.components.diagnostics import async_redact_data as _ha_async_redact_data
except ImportError:
    _ha_async_redact_data = None

from .const import DOMAIN
from .coordinator import AveVideo44Coordinator

TO_REDACT: Set[str] = {
    "account",
    "appSecret",
    "email",
    "jsessionid",
    "otp",
    "password",
    "sessionId",
    "session_id",
    "sip_password",
    "token",
}


def async_redact_data(data: Any, to_redact: Set[str] = TO_REDACT) -> Any:
    """Recursively redact sensitive keys from dictionary or iterable."""
    if _ha_async_redact_data is not None:
        return _ha_async_redact_data(data, to_redact)
    if isinstance(data, dict):
        return {
            key: "**REDACTED**" if key in to_redact else async_redact_data(val, to_redact)
            for key, val in data.items()
        }
    if isinstance(data, list):
        return [async_redact_data(item, to_redact) for item in data]
    return data


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> Dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: AveVideo44Coordinator = entry.runtime_data or hass.data.get(DOMAIN, {}).get("entries", {}).get(entry.entry_id)

    diag_data: Dict[str, Any] = {
        "entry": {
            "entry_id": entry.entry_id,
            "version": entry.version if hasattr(entry, "version") else 1,
            "data": async_redact_data(dict(entry.data)),
            "options": async_redact_data(dict(entry.options)),
        },
    }

    if coordinator:
        diag_data["coordinator"] = {
            "call_state": coordinator.call_state,
            "active_caller_id": coordinator.active_caller_id,
            "active_caller_name": coordinator.active_caller_name,
            "devices_count": len(coordinator.devices),
            "devices": async_redact_data(coordinator.devices),
            "intercom_book": coordinator.intercom_book,
            "last_call_time": coordinator.last_call_time,
        }

    return diag_data
