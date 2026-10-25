"""WebSocket API commands for AVE Video V44 call control and audio streaming."""

import base64
import logging
from typing import Any, Dict, Optional
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .coordinator import AveVideo44Coordinator

_LOGGER = logging.getLogger(__name__)


def _get_coordinator(
    hass: HomeAssistant,
    entry_id: Optional[str] = None,
    device_id: Any = None,
) -> AveVideo44Coordinator:
    """Retrieve coordinator for entry_id or device_id, or first active coordinator."""
    entries = hass.data.get(DOMAIN, {}).get("entries", {})
    if entry_id and entry_id in entries:
        return entries[entry_id]

    if device_id is not None:
        dev_str = str(device_id)
        for coord in entries.values():
            for d in coord.devices:
                if str(d.get("deviceId")) == dev_str:
                    return coord

    if entries:
        return next(iter(entries.values()))

    raise websocket_api.WebSocketError("not_found", "No AVE Video V44 coordinator found")


@websocket_api.websocket_command({
    vol.Required("type"): "ave_video44/call_control",
    vol.Optional("entry_id"): str,
    vol.Required("device_id"): vol.Any(int, str),
    vol.Required("action"): vol.In(["answer", "hangup", "call", "unlock", "monitor"]),
    vol.Optional("room_code"): str,
    vol.Optional("lock_id", default="1"): vol.Any(int, str),
})
@websocket_api.async_response
async def ws_call_control(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Handle call control actions: answer, hangup, call intercom, unlock, and monitor."""
    try:
        coordinator = _get_coordinator(hass, msg.get("entry_id"), msg.get("device_id"))
    except Exception as err:
        connection.send_error(msg["id"], "not_found", str(err))
        return

    action = msg["action"]
    device_id = msg["device_id"]

    if action == "answer":
        await coordinator.async_answer_call(device_id)
    elif action == "hangup":
        await coordinator.async_hangup_call(device_id)
    elif action == "call":
        await coordinator.async_call_intercom(device_id, room_code=msg.get("room_code"))
    elif action == "unlock":
        await coordinator.async_unlock(device_id, lock_id=str(msg.get("lock_id", "1")))
    elif action == "monitor":
        rtsp_url = await coordinator.async_wake_camera(device_id)
        connection.send_result(msg["id"], {"success": True, "rtsp_url": rtsp_url})
        return

    connection.send_result(msg["id"], {"success": True})


@websocket_api.websocket_command({
    vol.Required("type"): "ave_video44/audio_tx",
    vol.Optional("entry_id"): str,
    vol.Required("device_id"): vol.Any(int, str),
    vol.Required("payload"): str,
})
@websocket_api.async_response
async def ws_audio_tx(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Receive PCM16 audio from Lovelace card and send to RTP engine."""
    coordinator = _get_coordinator(hass, msg.get("entry_id"), msg.get("device_id"))
    try:
        pcm16_data = base64.b64decode(msg["payload"])
        coordinator.sip_session.send_pcm16_frame(pcm16_data)
        connection.send_result(msg["id"], {"success": True})
    except Exception as err:
        _LOGGER.error("Failed to forward audio frame: %s", err)
        connection.send_error(msg["id"], "audio_tx_failed", str(err))


@websocket_api.websocket_command({
    vol.Required("type"): "ave_video44/audio_subscribe",
    vol.Optional("entry_id"): str,
    vol.Required("device_id"): vol.Any(int, str),
})
@websocket_api.async_response
async def ws_audio_subscribe(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Subscribe to incoming decoded PCM16 audio frames."""
    coordinator = _get_coordinator(hass, msg.get("entry_id"), msg.get("device_id"))

    @callback
    def _audio_rx_callback(pcm16_frame: bytes) -> None:
        b64_payload = base64.b64encode(pcm16_frame).decode("ascii")
        connection.send_event(msg["id"], {"payload": b64_payload})

    if hasattr(coordinator.sip_session, "add_rx_pcm16_callback"):
        coordinator.sip_session.add_rx_pcm16_callback(_audio_rx_callback)
    else:
        coordinator.sip_session.set_rx_pcm16_callback(_audio_rx_callback)

    @callback
    def _unsubscribe() -> None:
        if hasattr(coordinator.sip_session, "remove_rx_pcm16_callback"):
            coordinator.sip_session.remove_rx_pcm16_callback(_audio_rx_callback)
        else:
            coordinator.sip_session.set_rx_pcm16_callback(None)

    connection.subscriptions[msg["id"]] = _unsubscribe
    connection.send_result(msg["id"], {"subscribed": True})


def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """Register all AVE Video V44 websocket endpoints."""
    websocket_api.async_register_command(hass, ws_call_control)
    websocket_api.async_register_command(hass, ws_audio_tx)
    websocket_api.async_register_command(hass, ws_audio_subscribe)
