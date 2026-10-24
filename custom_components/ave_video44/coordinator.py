"""DataUpdateCoordinator for AVE Video V44 integration."""

from datetime import datetime, timezone
import logging
from typing import Any, Callable, Dict, List, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_ACCOUNT,
    CONF_INTERCOM_BOOK,
    CONF_PASSWORD,
    DEFAULT_PREFERRED_VIDEO_STREAM,
    DOMAIN,
)
from .core.api import AveCloudApi
from .core.mqtt import AveMqttListener
from .core.sip_session import AveSipSession

_LOGGER = logging.getLogger(__name__)


class AveVideo44Coordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Coordinates updates and state management for AVE Video V44."""

    def __init__(self, hass: HomeAssistant, entry: Any) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=None,
        )
        self.entry = entry
        self.entry_id = entry.entry_id

        session = None
        try:
            session = async_get_clientsession(hass)
        except Exception:
            pass

        self.api = AveCloudApi(
            session=session,
            token=entry.data.get("token"),
            session_id=entry.data.get("session_id"),
        )

        self.sip_session = AveSipSession()
        self.mqtt_listener: Optional[AveMqttListener] = None

        self.devices: List[Dict[str, Any]] = []
        self.call_state: str = "idle"
        self.active_caller_id: str = ""
        self.active_caller_name: str = ""
        self.active_device_id: Optional[str] = None
        self.last_call_time: Optional[str] = None
        self.last_ring_event: Optional[Dict[str, Any]] = None
        self.selected_intercom_targets: Dict[str, str] = {}
        self._ring_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []

        self.intercom_book: Dict[str, str] = self._parse_intercom_book()

    def _parse_intercom_book(self) -> Dict[str, str]:
        """Parse CONF_INTERCOM_BOOK string into code->name dictionary."""
        book_raw = (
            self.entry.options.get(CONF_INTERCOM_BOOK)
            or self.entry.data.get(CONF_INTERCOM_BOOK)
            or ""
        )
        book: Dict[str, str] = {}
        for entry in book_raw.split(","):
            if "=" in entry:
                code, name = entry.split("=", 1)
                code_str = code.strip()
                if code_str:
                    book[code_str] = name.strip()
        return book

    def update_intercom_book(self) -> None:
        """Refresh parsed book after options update."""
        self.intercom_book = self._parse_intercom_book()
        self.async_update_listeners()

    def resolve_caller_name(self, caller_id: str) -> str:
        """Resolve room code against intercom book or fallback to original id."""
        return self.intercom_book.get(caller_id, caller_id)

    def handle_incoming_call(
        self, caller_id: str, call_type: str, device_id: int | str
    ) -> None:
        """Process incoming call notification."""
        self.call_state = "ringing"
        self.active_caller_id = str(caller_id)
        self.active_caller_name = self.resolve_caller_name(self.active_caller_id)
        self.active_device_id = str(device_id)
        self.last_call_time = datetime.now(timezone.utc).isoformat()

        self.hass.bus.async_fire(
            "ave_video44_incoming_call",
            {
                "caller_id": self.active_caller_id,
                "caller_name": self.active_caller_name,
                "call_type": str(call_type),
                "device_id": device_id,
            },
        )
        self.async_update_listeners()

    def handle_ring_event(
        self, device_id: int | str, ring_type: str, caller_id: str = ""
    ) -> None:
        """Record and dispatch doorbell ring event."""
        self.last_ring_event = {
            "device_id": str(device_id),
            "ring_type": ring_type,
            "caller_id": caller_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for cb in list(self._ring_callbacks):
            try:
                cb(ring_type, self.last_ring_event)
            except Exception as err:
                _LOGGER.error("Error in ring callback: %s", err)
        self.async_update_listeners()

    def register_ring_callback(
        self, callback: Callable[[str, Dict[str, Any]], None]
    ) -> Callable[[], None]:
        """Register listener for ring events."""
        self._ring_callbacks.append(callback)
        return lambda: self._ring_callbacks.remove(callback) if callback in self._ring_callbacks else None

    async def async_call_intercom(
        self, device_id: int | str, room_code: Optional[str] = None
    ) -> None:
        """Initiate outbound intercom call."""
        target = room_code or self.selected_intercom_targets.get(str(device_id), "")
        _LOGGER.debug("Calling intercom target %s from device %s", target, device_id)
        self.call_state = "in_call"
        self.active_device_id = str(device_id)
        self.active_caller_id = target
        self.active_caller_name = self.resolve_caller_name(target)
        self.async_update_listeners()

    async def async_answer_call(self, device_id: int | str) -> None:
        """Accept active incoming call."""
        _LOGGER.debug("Answering call on device %s", device_id)
        self.call_state = "in_call"
        self.active_device_id = str(device_id)
        self.async_update_listeners()

    async def async_hangup_call(self, device_id: int | str) -> None:
        """Terminate active call."""
        _LOGGER.debug("Hanging up call on device %s", device_id)
        self.call_state = "idle"
        self.active_caller_id = ""
        self.active_caller_name = ""
        self.active_device_id = None
        self.async_update_listeners()

    async def async_unlock(self, device_id: int | str, lock_id: int | str = "1") -> None:
        """Unlock specified lock on device."""
        if self.api:
            await self.api.unlock(device_id=str(device_id), lock_id=str(lock_id))

    def get_rtsp_url(self, device_id: int | str) -> str:
        """Return RTSP streaming URL for requested monitor."""
        pref_stream = self.entry.options.get(
            "preferred_video_stream", DEFAULT_PREFERRED_VIDEO_STREAM
        )
        stream_path = "sub" if pref_stream == "sub_stream" else "main"

        for dev in self.devices:
            if str(dev.get("deviceId")) == str(device_id):
                ip = dev.get("ip")
                if ip:
                    return f"rtsp://{ip}:554/live/{stream_path}"

        return f"rtsp://127.0.0.1:554/live/{stream_path}"

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch updated device list and metadata from cloud API."""
        try:
            home_id = self.entry.data.get("home_id")
            devices = await self.api.get_devices(home_id=home_id)
            if devices:
                self.devices = devices
            return {str(d.get("deviceId")): d for d in self.devices}
        except Exception as err:
            raise UpdateFailed(f"Error fetching AVE devices: {err}") from err

    async def async_start(self) -> None:
        """Start background listeners (MQTT & SIP transport)."""
        session_id = self.entry.data.get("session_id")
        if session_id:
            device_ids = [str(d.get("deviceId")) for d in self.devices]
            self.mqtt_listener = AveMqttListener(
                session_id=session_id,
                device_ids=device_ids,
                on_event=self._on_mqtt_event,
            )
            await self.mqtt_listener.async_start()

    def _on_mqtt_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Dispatch push notifications from cloud MQTT thread-safely."""
        if hasattr(self.hass, "loop") and self.hass.loop:
            self.hass.loop.call_soon_threadsafe(
                self._handle_mqtt_event_on_loop, event_type, payload
            )
        else:
            self._handle_mqtt_event_on_loop(event_type, payload)

    def _handle_mqtt_event_on_loop(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Handle MQTT event on event loop."""
        dev_id = payload.get("deviceId") or self.active_device_id
        if event_type == "call_incoming":
            caller_id = payload.get("callerId") or payload.get("from", "intercom")
            call_type = payload.get("callType", "DEV_DOORSTATION")
            self.handle_incoming_call(caller_id, str(call_type), dev_id or "default")
            self.handle_ring_event(dev_id or "default", "doorstation_ring", str(caller_id))
        elif event_type == "call_ended":
            self.call_state = "idle"
            self.async_update_listeners()

    async def async_shutdown(self) -> None:
        """Disconnect MQTT client and close SIP transport."""
        if self.mqtt_listener:
            await self.mqtt_listener.async_stop()
            self.mqtt_listener = None

        await self.sip_session.async_close()
        await self.api.async_close()
