"""WebSocket API commands for AVE Video V44 call control and audio streaming."""

import base64
import logging
import time
from typing import Any, Dict, Optional
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .coordinator import AveVideo44Coordinator

_LOGGER = logging.getLogger(__name__)

_AUDIO_TX_SESSIONS: Dict[Any, Dict[str, Any]] = {}


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


def get_active_sip_session(coordinator: AveVideo44Coordinator, device_id: Any) -> Any:
    """Resolve active SIP session: CloudSipMediaSession for device, or fallback to LAN AveSipSession."""
    dev_str = str(device_id) if device_id is not None else ""
    if dev_str and hasattr(coordinator, "cloud_sip_sessions"):
        cloud_sess = coordinator.cloud_sip_sessions.get(dev_str)
        if cloud_sess and getattr(cloud_sess, "is_active", False):
            return cloud_sess

    if coordinator.sip_session and not getattr(coordinator.sip_session, "is_closed", True):
        return coordinator.sip_session

    return None


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
    vol.Optional("ack", default=False): vol.Any(bool, vol.Coerce(bool)),
})
@websocket_api.async_response
async def ws_audio_tx(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Receive PCM16 audio from Lovelace card and send to RTP engine."""
    coordinator = _get_coordinator(hass, msg.get("entry_id"), msg.get("device_id"))
    device_id = msg.get("device_id")
    try:
        session = get_active_sip_session(coordinator, device_id)
        if not session:
            if msg.get("ack", False):
                raise websocket_api.WebSocketError(
                    "not_found", f"No active SIP session for device {device_id}"
                )
            _LOGGER.debug("audio_tx dropped: no active SIP session for device %s", device_id)
            return

        pcm16_data = base64.b64decode(msg["payload"])
        now = time.monotonic()
        session_key = (id(connection), str(device_id))
        stats = _AUDIO_TX_SESSIONS.get(session_key)
        if not stats or (now - stats["last_active"] > 5.0):
            _LOGGER.debug(
                "audio_tx first frame device=%s bytes=%d",
                device_id,
                len(pcm16_data),
            )
            stats = {
                "frames": 1,
                "bytes": len(pcm16_data),
                "last_log": now,
                "last_frames": 0,
                "last_active": now,
            }
            _AUDIO_TX_SESSIONS[session_key] = stats
        else:
            stats["frames"] += 1
            stats["bytes"] += len(pcm16_data)
            stats["last_active"] = now
            if now - stats["last_log"] >= 5.0:
                elapsed = now - stats["last_log"]
                rate = (stats["frames"] - stats["last_frames"]) / elapsed if elapsed > 0 else 0.0
                _LOGGER.debug(
                    "audio_tx device=%s frames=%d bytes=%d rate=%.1f fps",
                    device_id,
                    stats["frames"],
                    stats["bytes"],
                    rate,
                )
                stats["last_log"] = now
                stats["last_frames"] = stats["frames"]

        if len(_AUDIO_TX_SESSIONS) > 32:
            stale = [k for k, v in _AUDIO_TX_SESSIONS.items() if now - v.get("last_active", 0.0) > 30.0]
            for k in stale:
                _AUDIO_TX_SESSIONS.pop(k, None)

        if hasattr(session, "send_pcm16_frame"):
            session.send_pcm16_frame(pcm16_data)
        elif hasattr(session, "send_audio_frame"):
            session.send_audio_frame(pcm16_data)

        if msg.get("ack", False):
            connection.send_result(msg["id"], {"success": True})
    except websocket_api.WebSocketError:
        if msg.get("ack", False):
            raise
        _LOGGER.debug("audio_tx WebSocketError suppressed in fire-and-forget mode")
    except Exception as err:
        _LOGGER.error("Failed to forward audio frame: %s", err)
        if msg.get("ack", False):
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
    device_id = msg.get("device_id")
    _LOGGER.debug("audio_subscribe registered device=%s", device_id)

    rx_frames = 0
    rx_bytes = 0
    last_log_time = time.monotonic()
    last_log_frames = 0

    @callback
    def _audio_rx_callback(pcm16_frame: bytes) -> None:
        nonlocal rx_frames, rx_bytes, last_log_time, last_log_frames
        rx_frames += 1
        rx_bytes += len(pcm16_frame)
        now = time.monotonic()
        if now - last_log_time >= 5.0:
            elapsed = now - last_log_time
            rate = (rx_frames - last_log_frames) / elapsed if elapsed > 0 else 0.0
            _LOGGER.debug(
                "audio_subscribe device=%s frames=%d bytes=%d rate=%.1f fps",
                device_id,
                rx_frames,
                rx_bytes,
                rate,
            )
            last_log_time = now
            last_log_frames = rx_frames

        b64_payload = base64.b64encode(pcm16_frame).decode("ascii")
        connection.send_event(msg["id"], {"payload": b64_payload})

    dev_str = str(device_id) if device_id is not None else ""
    target_session = get_active_sip_session(coordinator, device_id)
    if dev_str and hasattr(coordinator, "cloud_sip_sessions"):
        cloud_sess = coordinator.cloud_sip_sessions.get(dev_str)
        if cloud_sess and (target_session is None or target_session is coordinator.sip_session):
            target_session = cloud_sess

    if target_session and hasattr(target_session, "add_rx_pcm16_callback"):
        target_session.add_rx_pcm16_callback(_audio_rx_callback)
    elif target_session and hasattr(target_session, "set_rx_pcm16_callback"):
        target_session.set_rx_pcm16_callback(_audio_rx_callback)

    @callback
    def _unsubscribe() -> None:
        if target_session and hasattr(target_session, "remove_rx_pcm16_callback"):
            target_session.remove_rx_pcm16_callback(_audio_rx_callback)
        elif target_session and hasattr(target_session, "set_rx_pcm16_callback"):
            target_session.set_rx_pcm16_callback(None)

    connection.subscriptions[msg["id"]] = _unsubscribe
    connection.send_result(msg["id"], {"subscribed": True})


def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """Register all AVE Video V44 websocket endpoints."""
    websocket_api.async_register_command(hass, ws_call_control)
    websocket_api.async_register_command(hass, ws_audio_tx)
    websocket_api.async_register_command(hass, ws_audio_subscribe)
