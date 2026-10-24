"""The AVE Video V44 Home Assistant integration."""

import logging
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
try:
    from homeassistant.components.http import StaticPathConfig
except ImportError:
    StaticPathConfig = None

from .const import DOMAIN
from .coordinator import AveVideo44Coordinator
from .websocket_api import async_register_websocket_commands

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.LOCK,
    Platform.BUTTON,
    Platform.BINARY_SENSOR,
    Platform.EVENT,
    Platform.SENSOR,
    Platform.SELECT,
    Platform.CAMERA,
]


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up AVE Video V44 global services and static card path."""
    hass.data.setdefault(DOMAIN, {"entries": {}, "ws_registered": False})

    if not hass.data[DOMAIN]["ws_registered"]:
        async_register_websocket_commands(hass)
        hass.data[DOMAIN]["ws_registered"] = True

    frontend_dir = Path(__file__).parent / "frontend"
    card_path = frontend_dir / "ave-video44-card.js"
    if hasattr(hass, "http") and hasattr(hass.http, "async_register_static_paths") and StaticPathConfig:
        try:
            await hass.http.async_register_static_paths([
                StaticPathConfig(
                    path=str(card_path),
                    url_path="/ave_video44_frontend/ave-video44-card.js",
                    cache_headers=True,
                )
            ])
            _LOGGER.debug("Registered static path for /ave_video44_frontend/ave-video44-card.js")
        except Exception as err:
            _LOGGER.debug("Could not register static path: %s", err)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AVE Video V44 from a config entry."""
    coordinator = AveVideo44Coordinator(hass, entry)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.warning("Initial cloud refresh warning: %s", err)

    await coordinator.async_start()

    entry.runtime_data = coordinator
    hass.data.setdefault(DOMAIN, {}).setdefault("entries", {})[entry.entry_id] = coordinator

    if hasattr(hass.config_entries, "async_forward_entry_setups"):
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _async_register_services(hass)

    if hasattr(entry, "add_update_listener") and hasattr(entry, "async_on_unload"):
        entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = True
    if hasattr(hass.config_entries, "async_unload_platforms"):
        unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator: AveVideo44Coordinator = getattr(
            entry, "runtime_data", None
        ) or hass.data.get(DOMAIN, {}).get("entries", {}).get(entry.entry_id)

        if coordinator:
            await coordinator.async_shutdown()

        hass.data.get(DOMAIN, {}).get("entries", {}).pop(entry.entry_id, None)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry on options change."""
    coordinator: AveVideo44Coordinator = getattr(
        entry, "runtime_data", None
    ) or hass.data.get(DOMAIN, {}).get("entries", {}).get(entry.entry_id)
    if coordinator:
        coordinator.update_intercom_book()
    await hass.config_entries.async_reload(entry.entry_id)


def _async_register_services(hass: HomeAssistant) -> None:
    """Register domain services."""
    if hass.services.has_service(DOMAIN, "unlock"):
        return

    def _get_coordinator(target_id: str | None) -> AveVideo44Coordinator | None:
        entries = hass.data.get(DOMAIN, {}).get("entries", {})
        if target_id and target_id in entries:
            return entries[target_id]
        if entries:
            return next(iter(entries.values()))
        return None

    async def async_service_unlock(call: ServiceCall) -> None:
        device_id = call.data.get("device_id")
        lock_id = call.data.get("lock_id", "1")
        entry_id = call.data.get("entry_id")
        coord = _get_coordinator(entry_id)
        if coord and coord.api:
            await coord.api.unlock(device_id=str(device_id), lock_id=str(lock_id))

    async def async_service_call_intercom(call: ServiceCall) -> None:
        device_id = call.data.get("device_id")
        room_code = call.data.get("room_code")
        entry_id = call.data.get("entry_id")
        coord = _get_coordinator(entry_id)
        if coord:
            await coord.async_call_intercom(device_id, room_code=room_code)

    async def async_service_answer_call(call: ServiceCall) -> None:
        device_id = call.data.get("device_id")
        entry_id = call.data.get("entry_id")
        coord = _get_coordinator(entry_id)
        if coord:
            await coord.async_answer_call(device_id)

    async def async_service_hangup_call(call: ServiceCall) -> None:
        device_id = call.data.get("device_id")
        entry_id = call.data.get("entry_id")
        coord = _get_coordinator(entry_id)
        if coord:
            await coord.async_hangup_call(device_id)

    services = {
        "unlock": async_service_unlock,
        "call_intercom": async_service_call_intercom,
        "answer_call": async_service_answer_call,
        "hangup_call": async_service_hangup_call,
    }
    for name, handler in services.items():
        hass.services.async_register(DOMAIN, name, handler)
