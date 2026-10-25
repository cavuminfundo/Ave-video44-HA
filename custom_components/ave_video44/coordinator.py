"""DataUpdateCoordinator for AVE Video V44 integration."""

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple
import urllib.parse

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
from .core.sip_session import AveSipSession, CloudSipMediaSession

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
        self.config_entry = entry
        self.entry_id = entry.entry_id
        self.home_id = entry.data.get("home_id") if getattr(entry, "data", None) else None

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
        self.cloud_sip_sessions: Dict[str, CloudSipMediaSession] = {}
        self._wake_events: Dict[str, asyncio.Event] = {}
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
        self.active_rtsp_url: Optional[str] = None
        self._last_rtsp_auth: Optional[Tuple[str, str, str, str, int]] = None

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

    async def async_wait_for_wake(self, device_id: int | str, timeout: float = 10.0) -> None:
        """Wait for an ongoing wake_camera attempt to finish on this device."""
        ev = self._wake_events.get(str(device_id))
        if ev and not ev.is_set():
            try:
                await asyncio.wait_for(ev.wait(), timeout=timeout)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass

    async def async_wake_camera(
        self, device_id: int | str, monitoring_device_number: Optional[str] = None
    ) -> Optional[str]:
        """Wake outdoor camera / start live monitoring session."""
        _LOGGER.debug("Waking camera for device %s", device_id)
        dev_str = str(device_id)
        wake_ev = asyncio.Event()
        self._wake_events[dev_str] = wake_ev

        try:
            dev = next((d for d in self.devices if str(d.get("deviceId")) == dev_str), None)
            mon_num = monitoring_device_number
            if not mon_num:
                if dev and isinstance(dev.get("extraConfig"), dict):
                    mon_num = str(dev["extraConfig"].get("deviceNumber", "1"))
                else:
                    mon_num = "1"

            # Check for Cloud SIP session (TS-SMART 2-wire intercom)
            intercom_info = dev.get("deviceIntercomInfo") if dev else None
            target_sip_uri = None
            if isinstance(intercom_info, dict):
                u = intercom_info.get("username", "")
                if str(u).startswith("sip:"):
                    target_sip_uri = str(u)
            elif isinstance(intercom_info, list) and intercom_info:
                for item in intercom_info:
                    if isinstance(item, dict):
                        u = item.get("username", "")
                        if str(u).startswith("sip:"):
                            target_sip_uri = str(u)
                            break

            started_sip = False
            if target_sip_uri and self.api:
                if dev_str in self.cloud_sip_sessions:
                    old_sess = self.cloud_sip_sessions.pop(dev_str)
                    try:
                        await old_sess.async_stop()
                    except Exception:
                        pass

                try:
                    sip_acct = await self.api.get_sip_account(dev_str)
                    if isinstance(sip_acct, dict) and sip_acct.get("username") and sip_acct.get("password"):
                        user_id = str(
                            (dev.get("userId") if dev else None)
                            or (dev.get("createUser") if dev else None)
                            or (self.entry.data.get("user_id") if getattr(self, "entry", None) and getattr(self.entry, "data", None) else None)
                            or "34964"
                        )
                        ffmpeg_bin = "ffmpeg"
                        try:
                            from homeassistant.components.ffmpeg import DATA_FFMPEG
                            if hasattr(self, "hass") and self.hass and DATA_FFMPEG in self.hass.data:
                                ffmpeg_bin = getattr(self.hass.data[DATA_FFMPEG], "binary", "ffmpeg")
                        except Exception:
                            pass

                        session = CloudSipMediaSession(
                            device_id=dev_str,
                            sip_username=str(sip_acct["username"]),
                            sip_password=str(sip_acct["password"]),
                            target_sip_uri=target_sip_uri,
                            user_id=user_id,
                            target_device_num=str(mon_num or "1"),
                            sender_name="Citofono",
                            ffmpeg_binary=ffmpeg_bin,
                        )
                        self.cloud_sip_sessions[dev_str] = session
                        started_sip = await session.async_start()
                except Exception as sip_err:
                    _LOGGER.debug("Could not start CloudSipMediaSession: %s", sip_err)

            if started_sip:
                self.active_rtsp_url = None
                self.active_device_id = dev_str
                self.call_state = "monitoring"
                self.async_update_listeners()
                return target_sip_uri

            call_id = None
            if self.api:
                try:
                    call_id = await self.api.control_monitoring(
                        device_id,
                        monitoring_device_number=mon_num,
                        action=1,
                        resolution_level=0,
                    )
                except Exception as err:
                    _LOGGER.error("Failed to start camera monitoring on API: %s", err)

            scheme = "rtsps"
            domain = "eu-video.gvs-icloud.com"
            port = 8322
            user = ""
            pwd = ""

            if self.api:
                try:
                    rtsp_cfg = await self.api.get_rtsp_config()
                    if isinstance(rtsp_cfg, dict):
                        auth = rtsp_cfg.get("auth")
                        if isinstance(auth, dict):
                            basic = auth.get("basic")
                            if isinstance(basic, dict):
                                user = basic.get("username") or ""
                                pwd = basic.get("password") or ""
                        if not user:
                            user = rtsp_cfg.get("account") or rtsp_cfg.get("username") or ""
                        if not pwd:
                            pwd = rtsp_cfg.get("password") or ""

                        endpoints = rtsp_cfg.get("serverEndpoints")
                        if isinstance(endpoints, list) and endpoints:
                            ep0 = endpoints[0]
                            if isinstance(ep0, dict):
                                domain = ep0.get("domain") or domain
                                ports_val = ep0.get("ports")
                                if isinstance(ports_val, str):
                                    try:
                                        ports_val = json.loads(ports_val)
                                    except Exception:
                                        pass
                                if isinstance(ports_val, dict):
                                    port = ports_val.get("rtsps") or ports_val.get("rtsp") or port
                        else:
                            domain = rtsp_cfg.get("domain") or domain
                            port = rtsp_cfg.get("port") or port
                except Exception as err:
                    _LOGGER.debug("Error fetching rtsp config: %s", err)

            user_enc = urllib.parse.quote(str(user), safe="") if user else ""
            pwd_enc = urllib.parse.quote(str(pwd), safe="") if pwd else ""
            target_num = mon_num or "1"
            target_enc = urllib.parse.quote(str(target_num), safe="")

            self._last_rtsp_auth = (scheme, user_enc, pwd_enc, domain, port)

            auth_part = f"{user_enc}:{pwd_enc}@" if user_enc and pwd_enc else ""
            self.active_rtsp_url = f"{scheme}://{auth_part}{domain}:{port}/stream/1/{device_id}/0/{target_enc}"
            _LOGGER.debug("Active RTSP URL constructed for device %s (credentials redacted)", device_id)

            self.active_device_id = dev_str
            self.call_state = "monitoring"
            self.async_update_listeners()
            return self.active_rtsp_url
        finally:
            wake_ev.set()

    async def async_get_camera_frame(
        self, device_id: int | str, timeout: float = 6.0
    ) -> Optional[bytes]:
        """Get latest camera frame from active CloudSipMediaSession."""
        session = self.cloud_sip_sessions.get(str(device_id))
        if session and session.is_active:
            return await session.wait_for_first_frame(timeout=timeout)
        return None

    async def async_hangup_call(self, device_id: int | str) -> None:
        """Terminate active call or monitoring session."""
        _LOGGER.debug("Hanging up call/monitoring on device %s", device_id)
        dev_str = str(device_id)
        if dev_str in self.cloud_sip_sessions:
            sess = self.cloud_sip_sessions.pop(dev_str)
            try:
                await sess.async_stop()
            except Exception as err:
                _LOGGER.debug("Error stopping CloudSipMediaSession on hangup: %s", err)

        if self.api and (self.call_state == "monitoring" or self.active_rtsp_url):
            dev = next((d for d in self.devices if str(d.get("deviceId")) == str(device_id)), None)
            mon_num = "1"
            if dev and isinstance(dev.get("extraConfig"), dict):
                mon_num = str(dev["extraConfig"].get("deviceNumber", "1"))
            try:
                await self.api.control_monitoring(
                    device_id,
                    monitoring_device_number=mon_num,
                    action=3,
                )
            except Exception as err:
                _LOGGER.debug("Error stopping camera monitoring: %s", err)

        self.active_rtsp_url = None
        self.call_state = "idle"
        self.active_caller_id = ""
        self.active_caller_name = ""
        self.active_device_id = None
        self.async_update_listeners()

    def _extract_discovered_intercoms_from_devices(
        self, devices: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """Extract discovered intercom contacts from devices extraConfig and deviceIntercomInfo."""
        discovered: Dict[str, str] = {}
        for dev in devices:
            dev_id_str = str(dev.get("deviceId") or "")
            extra = dev.get("extraConfig")
            if isinstance(extra, dict):
                dev_num = extra.get("deviceNumber")
                if dev_num is not None:
                    name = extra.get("deviceName") or dev.get("deviceName") or "Citofono"
                    discovered[str(dev_num)] = str(name)

            intercom_info = dev.get("deviceIntercomInfo")
            if isinstance(intercom_info, list):
                for item in intercom_info:
                    if isinstance(item, dict):
                        item_dev_id = str(item.get("deviceId") or "")
                        if item_dev_id and item_dev_id == dev_id_str:
                            continue
                        ha_zone = str(item.get("haZone") or "")
                        username = str(item.get("username") or "")
                        dev_name = item.get("deviceName") or "Unità interna"
                        code = username or (f"010{ha_zone}" if ha_zone else "")
                        if code:
                            label = f"Zona {ha_zone} - {dev_name}" if ha_zone else str(dev_name)
                            discovered[code] = label
            elif isinstance(intercom_info, dict):
                item_dev_id = str(intercom_info.get("deviceId") or "")
                if not (item_dev_id and item_dev_id == dev_id_str):
                    ha_zone = str(intercom_info.get("haZone") or "")
                    username = str(intercom_info.get("username") or "")
                    dev_name = intercom_info.get("deviceName") or "Unità interna"
                    code = username or (f"010{ha_zone}" if ha_zone else "")
                    if code:
                        label = f"Zona {ha_zone} - {dev_name}" if ha_zone else str(dev_name)
                        discovered[code] = label
        return discovered

    async def async_discover_intercoms(self) -> Dict[str, str]:
        """Discover intercom and doorstation contacts from cloud and local devices."""
        discovered = self._extract_discovered_intercoms_from_devices(self.devices)
        if self.api:
            for dev in self.devices:
                dev_id = dev.get("deviceId")
                if dev_id:
                    try:
                        mon_list = await self.api.get_monitoring_list(str(dev_id))
                        if isinstance(mon_list, list):
                            for item in mon_list:
                                if isinstance(item, dict):
                                    num = item.get("deviceNumber")
                                    name = item.get("name") or item.get("deviceName")
                                    if num is not None and name:
                                        discovered[str(num)] = str(name)
                    except Exception as err:
                        _LOGGER.debug("Error querying monitoring list for %s: %s", dev_id, err)
        return discovered

    async def async_unlock(self, device_id: int | str, lock_id: int | str = "1") -> None:
        """Unlock specified lock on device."""
        if self.api:
            await self.api.unlock(device_id=str(device_id), lock_id=str(lock_id))

    def get_rtsp_url(self, device_id: int | str) -> Optional[str]:
        """Return RTSP streaming URL for requested monitor."""
        pref_stream = self.entry.options.get(
            "preferred_video_stream", DEFAULT_PREFERRED_VIDEO_STREAM
        )
        stream_path = "sub" if pref_stream == "sub_stream" else "main"

        for dev in self.devices:
            if str(dev.get("deviceId")) == str(device_id):
                ip = dev.get("ip")
                if ip and ip not in ("127.0.0.1", "0.0.0.0", "localhost"):
                    return f"rtsp://{ip}:554/live/{stream_path}"

        if self.active_rtsp_url and str(self.active_device_id) == str(device_id):
            return self.active_rtsp_url

        return None

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch updated device list and metadata from cloud API with auto-healing."""
        try:
            account = self.config_entry.data.get(CONF_ACCOUNT) if self.config_entry else None
            password = self.config_entry.data.get(CONF_PASSWORD) if self.config_entry else None

            if (not self.api.session_id and not self.api.token) or self.home_id in (None, 1, "1"):
                if account and password:
                    try:
                        login_data = await self.api.login_with_password(account, password)
                        new_home_id = self.home_id
                        new_home_name = self.config_entry.data.get("home_name", "Casa") if self.config_entry else "Casa"
                        if self.home_id in (None, 1, "1"):
                            homes = await self.api.get_home_list()
                            if homes:
                                new_home_id = homes[0].get("homeId", self.home_id)
                                new_home_name = homes[0].get("homeName", new_home_name)
                                self.home_id = new_home_id

                        if self.config_entry and hasattr(self.hass, "config_entries") and hasattr(self.hass.config_entries, "async_update_entry"):
                            new_data = dict(self.config_entry.data)
                            new_data["token"] = self.api.token or login_data.get("token")
                            new_data["session_id"] = self.api.session_id or login_data.get("sessionId")
                            new_data["home_id"] = new_home_id
                            new_data["home_name"] = new_home_name
                            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
                    except Exception as err:
                        _LOGGER.warning("Coordinator auto-heal login failed: %s", err)

            home_id = self.home_id or (self.entry.data.get("home_id") if self.entry else None)
            devices = await self.api.get_devices(home_id=home_id)

            if not devices and account and password:
                try:
                    login_data = await self.api.login_with_password(account, password)
                    if self.config_entry and hasattr(self.hass, "config_entries") and hasattr(self.hass.config_entries, "async_update_entry"):
                        new_data = dict(self.config_entry.data)
                        new_data["token"] = self.api.token or login_data.get("token")
                        new_data["session_id"] = self.api.session_id or login_data.get("sessionId")
                        self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
                    devices = await self.api.get_devices(home_id=home_id)
                except Exception as err:
                    _LOGGER.debug("Re-login attempt on empty devices failed: %s", err)

            if devices:
                normalized_devices: List[Dict[str, Any]] = []
                for d in devices:
                    dev = dict(d) if isinstance(d, dict) else {}
                    dev["deviceId"] = str(dev.get("deviceId") or dev.get("id") or "")
                    dev["deviceName"] = dev.get("deviceName") or dev.get("name") or "AVE V44"
                    dev["deviceModel"] = dev.get("deviceModel") or dev.get("className") or "TS-SMART"
                    dev["firmwareVersion"] = dev.get("firmwareVersion") or dev.get("version") or "1.0"
                    dev["online"] = dev.get("online", True)
                    dev["isOnline"] = 1 if dev.get("online", True) else 0
                    if "extraConfig" in d and "extraConfig" not in dev:
                        dev["extraConfig"] = d["extraConfig"]
                    if "deviceIntercomInfo" in d and "deviceIntercomInfo" not in dev:
                        dev["deviceIntercomInfo"] = d["deviceIntercomInfo"]
                    normalized_devices.append(dev)
                self.devices = normalized_devices

                if not self.intercom_book:
                    auto_discovered = self._extract_discovered_intercoms_from_devices(self.devices)
                    if auto_discovered:
                        self.intercom_book = auto_discovered

            if not self.devices:
                try:
                    from homeassistant.helpers import device_registry as dr
                    dev_reg = dr.async_get(self.hass)
                    entries = dr.async_entries_for_config_entry(dev_reg, self.entry_id)
                    recovered: List[Dict[str, Any]] = []
                    for dev_entry in entries:
                        for ident_domain, ident_id in dev_entry.identifiers:
                            if ident_domain == DOMAIN and ident_id:
                                recovered.append({
                                    "deviceId": str(ident_id),
                                    "deviceName": dev_entry.name or dev_entry.original_name or "Unità interna AVE",
                                    "deviceModel": dev_entry.model or "TS-SMART",
                                    "firmwareVersion": dev_entry.sw_version or "1.0",
                                    "online": True,
                                    "isOnline": 1,
                                })
                    if recovered:
                        self.devices = recovered
                except Exception as dr_err:
                    _LOGGER.debug("Device registry fallback check: %s", dr_err)

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

    def _on_mqtt_event(
        self, event_type_or_payload: Any, payload: Optional[Dict[str, Any]] = None
    ) -> None:
        """Dispatch push notifications from cloud MQTT thread-safely."""
        if payload is None and isinstance(event_type_or_payload, dict):
            payload = event_type_or_payload
            event_type = str(payload.get("code") or "unknown")
        else:
            event_type = str(event_type_or_payload)
            payload = payload or {}

        if hasattr(self.hass, "loop") and self.hass.loop:
            self.hass.loop.call_soon_threadsafe(
                self._handle_mqtt_event_on_loop, event_type, payload
            )
        else:
            self._handle_mqtt_event_on_loop(event_type, payload)

    def _handle_mqtt_event_on_loop(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Handle MQTT event on event loop."""
        code = payload.get("code") or event_type
        action = payload.get("action")
        dev_id = payload.get("deviceId") or self.active_device_id

        if code == "monitoring" and action == 1:
            value = payload.get("value")
            server_url = None
            if isinstance(value, dict):
                res = value.get("result")
                if isinstance(res, dict):
                    server_url = res.get("serverUrl") or res.get("server_url")
                elif isinstance(res, str):
                    server_url = res
            if not server_url:
                server_url = payload.get("serverUrl")

            if server_url and "/stream" in server_url:
                stream_path = server_url[server_url.index("/stream"):]
                if self._last_rtsp_auth:
                    scheme, user_enc, pwd_enc, domain, port = self._last_rtsp_auth
                    auth_part = f"{user_enc}:{pwd_enc}@" if user_enc and pwd_enc else ""
                    self.active_rtsp_url = f"{scheme}://{auth_part}{domain}:{port}{stream_path}"
                else:
                    self.active_rtsp_url = f"rtsps://eu-video.gvs-icloud.com:8322{stream_path}"

            self.call_state = "monitoring"
            if dev_id:
                self.active_device_id = str(dev_id)
            self.async_update_listeners()
            return

        if code == "monitoring" and action in (0, 3):
            self.active_rtsp_url = None
            self.call_state = "idle"
            self.async_update_listeners()
            return

        if event_type == "call_incoming":
            caller_id = payload.get("callerId") or payload.get("from", "intercom")
            call_type = payload.get("callType", "DEV_DOORSTATION")
            self.handle_incoming_call(caller_id, str(call_type), dev_id or "default")
            self.handle_ring_event(dev_id or "default", "doorstation_ring", str(caller_id))
        elif event_type == "call_ended":
            self.active_rtsp_url = None
            self.call_state = "idle"
            self.async_update_listeners()

    async def async_shutdown(self) -> None:
        """Disconnect MQTT client and close SIP transport."""
        for sess in list(self.cloud_sip_sessions.values()):
            try:
                await sess.async_stop()
            except Exception:
                pass
        self.cloud_sip_sessions.clear()

        if self.mqtt_listener:
            await self.mqtt_listener.async_stop()
            self.mqtt_listener = None

        await self.sip_session.async_close()
        await self.api.async_close()
