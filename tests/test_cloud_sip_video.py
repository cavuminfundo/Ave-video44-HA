"""Tests for Cloud SIP Media Session, H.264 SRTP decoding, and camera streaming."""

import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import sys
from types import ModuleType
from typing import Any

# Ensure voluptuous stub is registered in sys.modules
try:
    import voluptuous as vol
except ImportError:
    vol_mod = ModuleType("voluptuous")
    class Schema:
        def __init__(self, schema): self.schema = schema
        def __call__(self, val): return val
    vol_mod.Schema = Schema
    vol_mod.Required = lambda k, default=None: k
    vol_mod.Optional = lambda k, default=None: k
    vol_mod.In = lambda items: items
    vol_mod.Any = lambda *args: lambda val: val
    vol_mod.Coerce = lambda t: lambda val: val
    sys.modules.setdefault("voluptuous", vol_mod)
    import voluptuous as vol

# Ensure homeassistant stubs exist in sys.modules
def _ensure_ha_stubs():
    if "homeassistant" in sys.modules and not isinstance(sys.modules["homeassistant"], MagicMock):
        return

    ha_mod = ModuleType("homeassistant")
    ha_mod.__path__ = []
    core_mod = ModuleType("homeassistant.core")
    config_entries_mod = ModuleType("homeassistant.config_entries")
    const_mod = ModuleType("homeassistant.const")
    exceptions_mod = ModuleType("homeassistant.exceptions")
    helpers_mod = ModuleType("homeassistant.helpers")
    helpers_mod.__path__ = []
    cv_mod = ModuleType("homeassistant.helpers.config_validation")
    cv_mod.config_entry_only_config_schema = lambda domain: lambda config: config
    helpers_mod.config_validation = cv_mod
    entity_mod = ModuleType("homeassistant.helpers.entity")
    update_coordinator_mod = ModuleType("homeassistant.helpers.update_coordinator")
    aiohttp_client_mod = ModuleType("homeassistant.helpers.aiohttp_client")
    dispatcher_mod = ModuleType("homeassistant.helpers.dispatcher")
    device_registry_mod = ModuleType("homeassistant.helpers.device_registry")
    entity_platform_mod = ModuleType("homeassistant.helpers.entity_platform")
    entity_platform_mod.AddEntitiesCallback = Any
    components_mod = ModuleType("homeassistant.components")
    components_mod.__path__ = []
    lock_mod = ModuleType("homeassistant.components.lock")
    button_mod = ModuleType("homeassistant.components.button")
    binary_sensor_mod = ModuleType("homeassistant.components.binary_sensor")
    event_mod = ModuleType("homeassistant.components.event")
    sensor_mod = ModuleType("homeassistant.components.sensor")
    select_mod = ModuleType("homeassistant.components.select")
    camera_mod = ModuleType("homeassistant.components.camera")
    websocket_api_mod = ModuleType("homeassistant.components.websocket_api")
    http_mod = ModuleType("homeassistant.components.http")
    ffmpeg_mod = ModuleType("homeassistant.components.ffmpeg")
    ffmpeg_mod.DATA_FFMPEG = "ffmpeg"
    ffmpeg_mod.async_get_image = AsyncMock(return_value=b"test_image")
    components_mod.ffmpeg = ffmpeg_mod

    class HomeAssistant:
        def __init__(self):
            self.data = {}
            self.services = MagicMock()
            self.bus = MagicMock()
            self.http = MagicMock()
            self.config_entries = MagicMock()
            self.loop = MagicMock()
            self.loop.call_soon_threadsafe = lambda func, *args: func(*args)

    def callback(func):
        return func

    core_mod.HomeAssistant = HomeAssistant
    core_mod.callback = callback
    core_mod.ServiceCall = MagicMock()
    core_mod.Event = MagicMock()

    class ConfigFlow:
        def __init_subclass__(cls, domain=None, **kwargs):
            cls.domain = domain
            super().__init_subclass__()
        def async_show_form(self, *, step_id, data_schema=None, errors=None, description_placeholders=None):
            return {"type": "form", "step_id": step_id, "data_schema": data_schema, "errors": errors or {}, "description_placeholders": description_placeholders}
        def async_create_entry(self, *, title, data, options=None):
            return {"type": "create_entry", "title": title, "data": data, "options": options or {}}
        def async_abort(self, *, reason):
            return {"type": "abort", "reason": reason}
        async def async_set_unique_id(self, unique_id):
            self.unique_id = unique_id
        def _abort_if_unique_id_configured(self):
            pass

    class OptionsFlow:
        def __init__(self, config_entry=None):
            self.config_entry = config_entry
        def async_show_form(self, *, step_id, data_schema=None, errors=None):
            return {"type": "form", "step_id": step_id, "data_schema": data_schema, "errors": errors or {}}
        def async_create_entry(self, *, title, data):
            return {"type": "create_entry", "title": title, "data": data}

    class ConfigEntry:
        def __init__(self, entry_id="test_entry", data=None, options=None, unique_id=None):
            self.entry_id = entry_id
            self.data = data or {}
            self.options = options or {}
            self.unique_id = unique_id
            self.runtime_data = None

    config_entries_mod.ConfigFlow = ConfigFlow
    config_entries_mod.OptionsFlow = OptionsFlow
    config_entries_mod.ConfigEntry = ConfigEntry
    config_entries_mod.ConfigFlowResult = dict

    class Platform:
        LOCK = "lock"
        BUTTON = "button"
        BINARY_SENSOR = "binary_sensor"
        EVENT = "event"
        SENSOR = "sensor"
        SELECT = "select"
        CAMERA = "camera"

    const_mod.Platform = Platform
    const_mod.CONF_NAME = "name"
    const_mod.CONF_HOST = "host"
    const_mod.CONF_PORT = "port"
    const_mod.CONF_USERNAME = "username"
    const_mod.CONF_PASSWORD = "password"
    const_mod.STATE_LOCKED = "locked"
    const_mod.STATE_UNLOCKED = "unlocked"
    const_mod.ATTR_DEVICE_ID = "device_id"
    const_mod.ATTR_ENTITY_ID = "entity_id"

    class HomeAssistantError(Exception): pass
    class ConfigEntryNotReady(HomeAssistantError): pass
    class ConfigEntryAuthFailed(HomeAssistantError): pass
    exceptions_mod.HomeAssistantError = HomeAssistantError
    exceptions_mod.ConfigEntryNotReady = ConfigEntryNotReady
    exceptions_mod.ConfigEntryAuthFailed = ConfigEntryAuthFailed

    class Entity:
        def __init__(self):
            self.hass = None
            self.entity_id = None
            self._attr_name = None
            self._attr_unique_id = None
        async def async_added_to_hass(self): pass
        async def async_will_remove_from_hass(self): pass
        def async_write_ha_state(self): pass

    class DeviceInfo(dict):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

    entity_mod.Entity = Entity
    entity_mod.DeviceInfo = DeviceInfo
    device_registry_mod.DeviceInfo = DeviceInfo

    class DataUpdateCoordinator:
        def __class_getitem__(cls, item):
            return cls
        def __init__(self, hass, logger, name, update_interval=None):
            self.hass = hass
            self.logger = logger
            self.name = name
            self.data = None
            self._listeners = []
        def async_add_listener(self, update_callback):
            self._listeners.append(update_callback)
            return lambda: self._listeners.remove(update_callback) if update_callback in self._listeners else None
        def async_update_listeners(self):
            for listener in list(self._listeners):
                listener()
        async def async_config_entry_first_refresh(self): pass

    class CoordinatorEntity(Entity):
        def __class_getitem__(cls, item):
            return cls
        def __init__(self, coordinator):
            super().__init__()
            self.coordinator = coordinator
        @property
        def available(self):
            return True

    class UpdateFailed(HomeAssistantError): pass

    update_coordinator_mod.DataUpdateCoordinator = DataUpdateCoordinator
    update_coordinator_mod.CoordinatorEntity = CoordinatorEntity
    update_coordinator_mod.UpdateFailed = UpdateFailed

    aiohttp_client_mod.async_get_clientsession = MagicMock()
    dispatcher_mod.async_dispatcher_send = MagicMock()
    dispatcher_mod.async_dispatcher_connect = MagicMock(return_value=lambda: None)

    class LockEntity(Entity):
        def __init__(self):
            super().__init__()
            self._attr_is_locked = True
        @property
        def is_locked(self):
            return self._attr_is_locked

    class ButtonEntity(Entity): pass

    class BinarySensorDeviceClass:
        SOUND = "sound"
        CONNECTIVITY = "connectivity"

    class BinarySensorEntity(Entity):
        def __init__(self):
            super().__init__()
            self._attr_is_on = False
        @property
        def is_on(self):
            return self._attr_is_on

    class EventDeviceClass:
        DOORBELL = "doorbell"

    class EventEntity(Entity):
        def __init__(self):
            super().__init__()
            self._last_event_type = None
            self._last_event_data = None
        def _trigger_event(self, event_type, event_data=None):
            self._last_event_type = event_type
            self._last_event_data = event_data

    class SensorEntity(Entity):
        def __init__(self):
            super().__init__()
            self._attr_native_value = None
        @property
        def native_value(self):
            return self._attr_native_value

    class SelectEntity(Entity):
        def __init__(self):
            super().__init__()
            self._attr_current_option = None
            self._attr_options = []
        @property
        def current_option(self):
            return self._attr_current_option
        @property
        def options(self):
            return self._attr_options

    class CameraEntityFeature(int):
        STREAM = 1

    class Camera(Entity):
        def __init__(self):
            super().__init__()
            self.supported_features = CameraEntityFeature.STREAM
        async def stream_source(self): return None

    lock_mod.LockEntity = LockEntity
    button_mod.ButtonEntity = ButtonEntity
    binary_sensor_mod.BinarySensorEntity = BinarySensorEntity
    binary_sensor_mod.BinarySensorDeviceClass = BinarySensorDeviceClass
    event_mod.EventEntity = EventEntity
    event_mod.EventDeviceClass = EventDeviceClass
    sensor_mod.SensorEntity = SensorEntity
    select_mod.SelectEntity = SelectEntity
    camera_mod.Camera = Camera
    camera_mod.CameraEntityFeature = CameraEntityFeature

    websocket_api_mod.async_register_command = MagicMock()
    websocket_api_mod.websocket_command = lambda schema: lambda func: func
    websocket_api_mod.async_response = lambda func: func
    websocket_api_mod.ActiveConnection = MagicMock
    class WebSocketError(Exception): pass
    websocket_api_mod.WebSocketError = WebSocketError

    class StaticPathConfig:
        def __init__(self, path, url_path, cache_headers=True):
            self.path = path
            self.url_path = url_path
            self.cache_headers = cache_headers
    http_mod.StaticPathConfig = StaticPathConfig

    stubs = {
        "homeassistant": ha_mod,
        "homeassistant.core": core_mod,
        "homeassistant.config_entries": config_entries_mod,
        "homeassistant.const": const_mod,
        "homeassistant.exceptions": exceptions_mod,
        "homeassistant.helpers": helpers_mod,
        "homeassistant.helpers.config_validation": cv_mod,
        "homeassistant.helpers.entity": entity_mod,
        "homeassistant.helpers.device_registry": device_registry_mod,
        "homeassistant.helpers.entity_platform": entity_platform_mod,
        "homeassistant.helpers.update_coordinator": update_coordinator_mod,
        "homeassistant.helpers.aiohttp_client": aiohttp_client_mod,
        "homeassistant.helpers.dispatcher": dispatcher_mod,
        "homeassistant.components": components_mod,
        "homeassistant.components.lock": lock_mod,
        "homeassistant.components.button": button_mod,
        "homeassistant.components.binary_sensor": binary_sensor_mod,
        "homeassistant.components.event": event_mod,
        "homeassistant.components.sensor": sensor_mod,
        "homeassistant.components.select": select_mod,
        "homeassistant.components.camera": camera_mod,
        "homeassistant.components.websocket_api": websocket_api_mod,
        "homeassistant.components.http": http_mod,
        "homeassistant.components.ffmpeg": ffmpeg_mod,
    }
    for name, mod in stubs.items():
        sys.modules.setdefault(name, mod)

_ensure_ha_stubs()

from custom_components.ave_video44.const import (
    DEFAULT_MQTT_PORT,
    DEFAULT_MQTT_USER,
    DEFAULT_MQTT_PASS,
)
from custom_components.ave_video44.core.mqtt import AveMqttListener
from custom_components.ave_video44.core.sip_session import CloudSipMediaSession


def test_cloud_sip_digest_auth_and_packet_construction():
    """Verify digest calculation and SIP REGISTER/INVITE packet structures."""
    # 1. Digest response
    auth_header = CloudSipMediaSession._compute_digest_auth(
        username="2114136144349364224",
        realm="eu.open-sips.gvs-icloud.com",
        password="secret_password",
        method="REGISTER",
        uri="sip:eu.open-sips.gvs-icloud.com",
        nonce="671b569e00000001abcdef",
    )
    assert 'username="2114136144349364224"' in auth_header
    assert 'realm="eu.open-sips.gvs-icloud.com"' in auth_header
    assert 'nonce="671b569e00000001abcdef"' in auth_header
    assert 'response="' in auth_header

    # 2. Session initialization
    session = CloudSipMediaSession(
        device_id="677771932745207808",
        sip_username="sip:2114136144349364224@eu.open-sips.gvs-icloud.com",
        sip_password="secret_password",
        target_sip_uri="sip:2114136144349364225@eu.open-sips.gvs-icloud.com",
        user_id="34964",
        target_device_num="1",
        sender_name="Citofono",
    )

    # 3. Build REGISTER packet
    reg_pkt = session.build_register_packet(cseq=1, auth=None)
    assert reg_pkt.startswith("REGISTER sip:eu.open-sips.gvs-icloud.com SIP/2.0\r\n")
    assert "To: <sip:2114136144349364224@eu.open-sips.gvs-icloud.com>" in reg_pkt
    assert "From: <sip:2114136144349364224@eu.open-sips.gvs-icloud.com>;tag=" in reg_pkt
    assert "Call-ID:" in reg_pkt
    assert "CSeq: 1 REGISTER\r\n" in reg_pkt
    assert "Content-Length: 0\r\n\r\n" in reg_pkt

    # 4. Build INVITE packet with 14 custom headers & SRTP crypto SDP
    srtp_audio_key = "aXVsaWFuMTIzNDU2Nzg5MDEyMzQ1Njc4OTA="
    srtp_video_key = "dmlkZW8xMjM0NTY3ODkwMTIzNDU2Nzg5MDE="
    invite_pkt = session.build_invite_packet(
        cseq=1,
        local_ip="192.168.1.100",
        audio_port=18302,
        video_port=18304,
        srtp_audio_key=srtp_audio_key,
        srtp_video_key=srtp_video_key,
        auth_header=None,
    )

    # Check 14 headers
    assert "targetDeviceNum: 1" in invite_pkt
    assert "type: 0" in invite_pkt
    assert "callType: 0" in invite_pkt
    assert "iotCallVersion: 1.0.1" in invite_pkt
    assert "senderId: 34964" in invite_pkt
    assert "senderType: 3" in invite_pkt
    assert "senderName: Citofono" in invite_pkt
    assert "targetId: 677771932745207808" in invite_pkt
    assert "callId:" in invite_pkt
    assert "targetType: 1" in invite_pkt
    assert "enableVideo: 1" in invite_pkt
    assert "enableAudio: 1" in invite_pkt
    assert "proxyDeviceId: 677771932745207808" in invite_pkt
    assert "proxyFlag: 1" in invite_pkt

    # Check SDP
    assert "m=audio 18302 RTP/SAVP 8" in invite_pkt
    assert f"a=crypto:1 AES_CM_128_HMAC_SHA1_80 inline:{srtp_audio_key}" in invite_pkt
    assert "m=video 18304 RTP/SAVP 96" in invite_pkt
    assert f"a=crypto:1 AES_CM_128_HMAC_SHA1_80 inline:{srtp_video_key}" in invite_pkt


def test_cloud_sip_parse_200_ok_sdp_and_local_sdp():
    """Verify parsing remote SDP and generating local SDP for FFmpeg."""
    sdp_200 = (
        "v=0\r\n"
        "o=GVS 1000 1000 IN IP4 10.0.0.5\r\n"
        "s=Talk\r\n"
        "c=IN IP4 51.144.180.20\r\n"
        "t=0 0\r\n"
        "m=audio 25000 RTP/SAVP 8\r\n"
        "a=rtpmap:8 PCMA/8000\r\n"
        "a=crypto:1 AES_CM_128_HMAC_SHA1_80 inline:cmVtb3RlYXVkaW9rZXkxMjM0NTY3ODkwMTIzNDU2\r\n"
        "m=video 25002 RTP/SAVP 96\r\n"
        "a=rtpmap:96 H264/90000\r\n"
        "a=fmtp:96 profile-level-id=42e01f;packetization-mode=1\r\n"
        "a=crypto:1 AES_CM_128_HMAC_SHA1_80 inline:cmVtb3RldmlkZW9rZXkxMjM0NTY3ODkwMTIzNDU2\r\n"
    )

    parsed = CloudSipMediaSession.parse_200_ok_sdp(sdp_200)
    assert parsed["remote_ip"] == "51.144.180.20"
    assert parsed["remote_audio_port"] == 25000
    assert parsed["remote_video_port"] == 25002
    assert parsed["crypto_suite"] == "AES_CM_128_HMAC_SHA1_80"
    assert parsed["crypto_key"] == "cmVtb3RldmlkZW9rZXkxMjM0NTY3ODkwMTIzNDU2"
    assert "profile-level-id=42e01f" in parsed["video_fmtp"]

    session = CloudSipMediaSession(
        device_id="dev123",
        sip_username="sip:user@test.com",
        sip_password="pass",
        target_sip_uri="sip:target@test.com",
    )
    sdp_content = session._generate_local_sdp(
        ffmpeg_port=30000,
        crypto_suite=parsed["crypto_suite"],
        crypto_key=parsed["crypto_key"],
        video_fmtp=parsed["video_fmtp"],
    )
    assert "m=video 30000 RTP/SAVP 96" in sdp_content
    assert "a=rtpmap:96 H264/90000" in sdp_content
    assert f"a=fmtp:96 {parsed['video_fmtp']}" in sdp_content
    assert f"a=crypto:1 {parsed['crypto_suite']} inline:{parsed['crypto_key']}" in sdp_content


@pytest.mark.asyncio
async def test_cloud_sip_mjpeg_stream_frame_extraction():
    """Verify byte stream parser extracting JPEGs from image2pipe FFmpeg output."""
    session = CloudSipMediaSession(
        device_id="dev123",
        sip_username="sip:user@test.com",
        sip_password="pass",
        target_sip_uri="sip:target@test.com",
    )
    assert session.latest_frame is None
    assert session.frame_seq == 0

    frame1 = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00fake_frame_1\xff\xd9"
    frame2 = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00fake_frame_2\xff\xd9"

    # Chunk with partial frames and noise
    session._feed_mjpeg_bytes(b"garbage_header" + frame1[:10])
    assert session.latest_frame is None
    assert session.frame_seq == 0

    session._feed_mjpeg_bytes(frame1[10:] + b"noise" + frame2[:8])
    assert session.latest_frame == frame1
    assert session.frame_seq == 1

    first_frame = await session.wait_for_first_frame(timeout=1.0)
    assert first_frame == frame1

    # Second frame completes
    session._feed_mjpeg_bytes(frame2[8:] + b"trailing")
    assert session.latest_frame == frame2
    assert session.frame_seq == 2

    seq, next_frame = await session.wait_for_next_frame(last_seq=1, timeout=1.0)
    assert seq == 2
    assert next_frame == frame2


@pytest.mark.asyncio
async def test_coordinator_and_camera_cloud_sip_integration(mock_coordinator):
    """Verify coordinator starts CloudSipMediaSession and camera yields frames."""
    from custom_components.ave_video44.camera import AveVideo44Camera

    # Configure coordinator with TS-SMART SIP intercom info
    dev_id = 9991
    mock_coordinator.devices = [{
        "deviceId": dev_id,
        "deviceIntercomInfo": {
            "username": "sip:2114136144349364225@eu.open-sips.gvs-icloud.com",
            "roomCode": "1-1-101",
        },
        "userId": "34964",
    }]
    mock_coordinator.api.get_sip_account = AsyncMock(return_value={
        "username": "sip:2114136144349364224@eu.open-sips.gvs-icloud.com",
        "password": "sip_account_pass",
    })

    with patch("custom_components.ave_video44.coordinator.CloudSipMediaSession") as mock_session_cls:
        fake_session = MagicMock()
        fake_session.async_start = AsyncMock(return_value=True)
        fake_session.async_stop = AsyncMock()
        fake_session.wait_for_first_frame = AsyncMock(return_value=b"\xff\xd8fake_sip_frame\xff\xd9")
        fake_session.latest_frame = b"\xff\xd8fake_sip_frame\xff\xd9"
        fake_session.is_active = True
        mock_session_cls.return_value = fake_session

        # 1. Wake camera triggers cloud SIP session
        await mock_coordinator.async_wake_camera(device_id=dev_id)
        assert str(dev_id) in mock_coordinator.cloud_sip_sessions
        fake_session.async_start.assert_called_once()

        # 2. Coordinator retrieves frame
        frame = await mock_coordinator.async_get_camera_frame(dev_id)
        assert frame == b"\xff\xd8fake_sip_frame\xff\xd9"

        # 3. Camera entity returns frame
        cam = AveVideo44Camera(mock_coordinator, device_id=dev_id)
        from homeassistant.components.camera import CameraEntityFeature
        assert cam.supported_features == CameraEntityFeature.STREAM
        cam_frame = await cam.async_camera_image()
        assert cam_frame == b"\xff\xd8fake_sip_frame\xff\xd9"

        # 4. Hangup stops session
        await mock_coordinator.async_hangup_call(device_id=dev_id)
        fake_session.async_stop.assert_called_once()
        assert str(dev_id) not in mock_coordinator.cloud_sip_sessions


def test_mqtt_constants_and_default_credentials():
    """Verify MQTT port 18883 and smarthome_app default credentials."""
    assert DEFAULT_MQTT_PORT == 18883
    assert DEFAULT_MQTT_USER == "smarthome_app"
    assert DEFAULT_MQTT_PASS == "TYGHJK&*(&8923"

    listener = AveMqttListener(
        session_id="test_sess",
        home_id="12345",
        user_id="34964",
    )
    with patch("paho.mqtt.client.Client") as mock_client_cls:
        mock_paho = MagicMock()
        mock_client_cls.return_value = mock_paho
        asyncio.run(listener.async_start())
        mock_paho.username_pw_set.assert_called_with(
            username=DEFAULT_MQTT_USER,
            password=DEFAULT_MQTT_PASS,
        )
        asyncio.run(listener.async_stop())
