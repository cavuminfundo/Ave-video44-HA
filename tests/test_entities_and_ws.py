"""Tests for AVE Video V44 entities, coordinator, diagnostics, and WebSocket API."""

import asyncio
import base64
import sys
from types import ModuleType
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

# Ensure HA stubs exist in test environment
def _ensure_ha_stubs():
    if "homeassistant" in sys.modules and not isinstance(sys.modules["homeassistant"], MagicMock):
        return

    ha_mod = ModuleType("homeassistant")
    core_mod = ModuleType("homeassistant.core")
    ha_mod.__path__ = []
    config_entries_mod = ModuleType("homeassistant.config_entries")
    const_mod = ModuleType("homeassistant.const")
    exceptions_mod = ModuleType("homeassistant.exceptions")
    helpers_mod = ModuleType("homeassistant.helpers")
    helpers_mod.__path__ = []
    entity_mod = ModuleType("homeassistant.helpers.entity")
    update_coordinator_mod = ModuleType("homeassistant.helpers.update_coordinator")
    aiohttp_client_mod = ModuleType("homeassistant.helpers.aiohttp_client")
    dispatcher_mod = ModuleType("homeassistant.helpers.dispatcher")
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
            self._config_entry = config_entry
        @property
        def config_entry(self):
            return getattr(self, "_config_entry", None)
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
            self._attr_translation_key = None
            self._attr_icon = None
        @property
        def unique_id(self) -> str | None:
            return getattr(self, "_attr_unique_id", None)
        @property
        def translation_key(self) -> str | None:
            return getattr(self, "_attr_translation_key", None)
        @property
        def icon(self) -> str | None:
            return getattr(self, "_attr_icon", None)
        @property
        def entity_registry_enabled_default(self) -> bool:
            return getattr(self, "_attr_entity_registry_enabled_default", True)
        async def async_added_to_hass(self): pass
        async def async_will_remove_from_hass(self): pass
        def async_write_ha_state(self): pass

    class DeviceInfo(dict):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

    entity_mod.Entity = Entity
    entity_mod.DeviceInfo = DeviceInfo

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

    device_registry_mod = ModuleType("homeassistant.helpers.device_registry")
    device_registry_mod.DeviceInfo = DeviceInfo

    entity_registry_mod = ModuleType("homeassistant.helpers.entity_registry")
    class RegistryEntryDisabler:
        INTEGRATION = "integration"
        USER = "user"
    entity_registry_mod.RegistryEntryDisabler = RegistryEntryDisabler

    class RegistryEntry:
        def __init__(self, entity_id, unique_id, disabled_by=None):
            self.entity_id = entity_id
            self.unique_id = unique_id
            self.disabled_by = disabled_by
    entity_registry_mod.RegistryEntry = RegistryEntry

    class EntityRegistry:
        def __init__(self):
            self.entities = {}
        def async_update_entity(self, entity_id, disabled_by=None):
            if entity_id in self.entities:
                self.entities[entity_id].disabled_by = disabled_by
    entity_registry_mod.EntityRegistry = EntityRegistry
    entity_registry_mod.async_get = lambda hass: getattr(hass, "_entity_registry", None) or EntityRegistry()

    class StaticPathConfig:
        def __init__(self, path, url_path, cache_headers=True):
            self.path = path
            self.url_path = url_path
            self.cache_headers = cache_headers
    http_mod.StaticPathConfig = StaticPathConfig

    config_validation_mod = ModuleType("homeassistant.helpers.config_validation")
    config_validation_mod.empty_config_schema = lambda domain: lambda x: x
    config_validation_mod.config_entry_only_config_schema = lambda domain: lambda x: x
    config_validation_mod.boolean = bool
    config_validation_mod.string = str
    config_validation_mod.positive_int = int

    stubs = {
        "homeassistant": ha_mod,
        "homeassistant.core": core_mod,
        "homeassistant.config_entries": config_entries_mod,
        "homeassistant.const": const_mod,
        "homeassistant.exceptions": exceptions_mod,
        "homeassistant.helpers": helpers_mod,
        "homeassistant.helpers.config_validation": config_validation_mod,
        "homeassistant.helpers.entity": entity_mod,
        "homeassistant.helpers.device_registry": device_registry_mod,
        "homeassistant.helpers.entity_registry": entity_registry_mod,
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
        sys.modules[name] = mod

_ensure_ha_stubs()

def _ensure_entity_registry():
    if "homeassistant.helpers.entity_registry" not in sys.modules:
        from types import ModuleType
        entity_registry_mod = ModuleType("homeassistant.helpers.entity_registry")
        class RegistryEntryDisabler:
            INTEGRATION = "integration"
            USER = "user"
        entity_registry_mod.RegistryEntryDisabler = RegistryEntryDisabler

        class RegistryEntry:
            def __init__(self, entity_id, unique_id, disabled_by=None):
                self.entity_id = entity_id
                self.unique_id = unique_id
                self.disabled_by = disabled_by
        entity_registry_mod.RegistryEntry = RegistryEntry

        class EntityRegistry:
            def __init__(self):
                self.entities = {}
            def async_update_entity(self, entity_id, disabled_by=None):
                if entity_id in self.entities:
                    self.entities[entity_id].disabled_by = disabled_by
        entity_registry_mod.EntityRegistry = EntityRegistry
        entity_registry_mod.async_get = lambda hass: getattr(hass, "_entity_registry", None) or EntityRegistry()

        sys.modules["homeassistant.helpers.entity_registry"] = entity_registry_mod
        if "homeassistant.helpers" in sys.modules:
            setattr(sys.modules["homeassistant.helpers"], "entity_registry", entity_registry_mod)

_ensure_entity_registry()

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.camera import CameraEntityFeature

from custom_components.ave_video44.const import (
    CONF_ACCOUNT,
    CONF_INTERCOM_BOOK,
    CONF_PASSWORD,
    CONF_UNLOCK_PULSE_DURATION,
    DOMAIN,
)
from custom_components.ave_video44.coordinator import AveVideo44Coordinator
from custom_components.ave_video44.diagnostics import async_redact_data
from custom_components.ave_video44.lock import AveVideo44Lock
from custom_components.ave_video44.button import (
    AveVideo44AnswerButton,
    AveVideo44CallButton,
    AveVideo44HangupButton,
    AveVideo44UnlockButton,
    AveVideo44WakeCameraButton,
)
from custom_components.ave_video44.binary_sensor import (
    AveVideo44IncomingCallBinarySensor,
    AveVideo44OnlineBinarySensor,
)
from custom_components.ave_video44.event import AveVideo44DoorbellEvent
from custom_components.ave_video44.sensor import (
    AveVideo44CallStatusSensor,
    AveVideo44CallerNameSensor,
    AveVideo44LastCallSensor,
)
from custom_components.ave_video44.select import AveVideo44IntercomTargetSelect
from custom_components.ave_video44.camera import AveVideo44Camera
import custom_components.ave_video44.websocket_api as ws_api


@pytest.fixture
def mock_hass():
    hass = HomeAssistant()
    hass.bus.async_fire = MagicMock()
    hass.services.async_register = MagicMock()
    hass.loop = MagicMock()
    hass.loop.call_soon_threadsafe = lambda func, *args: func(*args)
    return hass


@pytest.fixture
def mock_entry():
    return ConfigEntry(
        entry_id="test_entry_id",
        data={CONF_ACCOUNT: "test@example.com", CONF_PASSWORD: "secret_password", "home_id": 101},
        options={
            CONF_INTERCOM_BOOK: "1-1-101=Piano Terra, 1-1-102=Primo Piano, 1-1-103=Cugino",
            CONF_UNLOCK_PULSE_DURATION: 2,
        },
        unique_id="ave_101",
    )


@pytest.fixture
def mock_coordinator(mock_hass, mock_entry):
    coord = AveVideo44Coordinator(mock_hass, mock_entry)
    coord.api = MagicMock()
    coord.api.unlock = AsyncMock(return_value=True)
    coord.api.async_close = AsyncMock()
    coord.sip_session = MagicMock()
    async def _mock_close():
        coord.sip_session.is_closed = True
    coord.sip_session.async_close = AsyncMock(side_effect=_mock_close)
    coord.sip_session.send_pcm16_frame = MagicMock()
    coord.sip_session.set_rx_pcm16_callback = MagicMock()
    coord.sip_session.add_rx_pcm16_callback = MagicMock()
    coord.sip_session.remove_rx_pcm16_callback = MagicMock()
    coord.sip_session.build_housetohouse_invite = MagicMock(return_value=b"INVITE sip:1-1-103 SIP/2.0")
    coord.sip_session.build_unlock_info = MagicMock(return_value=b"INFO sip:1-1-103 SIP/2.0")
    coord.sip_session.is_closed = False
    coord.devices = [
        {
            "deviceId": 9991,
            "deviceName": "Posto Interno TS-SMART",
            "deviceModel": "TS-SMART",
            "isOnline": 1,
            "ip": "192.168.1.100",
            "mac": "AA:BB:CC:DD:EE:01",
            "serialNumber": "SN9991",
        }
    ]
    return coord


# --- Coordinator Tests ---

@pytest.mark.asyncio
async def test_coordinator_caller_id_resolution(mock_coordinator):
    """Test resolution of room code to friendly name using intercom book."""
    assert mock_coordinator.resolve_caller_name("1-1-101") == "Piano Terra"
    assert mock_coordinator.resolve_caller_name("1-1-103") == "Cugino"
    assert mock_coordinator.resolve_caller_name("1-1-999") == "1-1-999"


@pytest.mark.asyncio
async def test_coordinator_call_state_transitions(mock_coordinator, mock_hass):
    """Test call states idle -> ringing -> in_call -> idle and event firing."""
    assert mock_coordinator.call_state == "idle"

    # Trigger incoming call
    mock_coordinator.handle_incoming_call(caller_id="1-1-101", call_type="DEV_DOORSTATION", device_id=9991)
    assert mock_coordinator.call_state == "ringing"
    assert mock_coordinator.active_caller_id == "1-1-101"
    assert mock_coordinator.active_caller_name == "Piano Terra"

    # Verify event fired on bus
    mock_hass.bus.async_fire.assert_called_with(
        "ave_video44_incoming_call",
        {
            "caller_id": "1-1-101",
            "caller_name": "Piano Terra",
            "call_type": "DEV_DOORSTATION",
            "device_id": 9991,
        },
    )

    # Answer call
    await mock_coordinator.async_answer_call(device_id=9991)
    assert mock_coordinator.call_state == "in_call"

    # Hangup call
    await mock_coordinator.async_hangup_call(device_id=9991)
    assert mock_coordinator.call_state == "idle"


@pytest.mark.asyncio
async def test_coordinator_shutdown(mock_coordinator):
    """Test coordinator clean shutdown."""
    mqtt_mock = MagicMock()
    mqtt_mock.async_stop = AsyncMock()
    mock_coordinator.mqtt_listener = mqtt_mock
    sip_mock = mock_coordinator.sip_session
    sip_mock.is_closed = False

    await mock_coordinator.async_shutdown()
    assert sip_mock.is_closed is True
    assert mock_coordinator.mqtt_listener is None
    mqtt_mock.async_stop.assert_called_once()
    mock_coordinator.api.async_close.assert_called_once()


# --- Platform Entities Tests ---

@pytest.mark.asyncio
async def test_lock_entity_pedestrian_and_driveway(mock_coordinator):
    """Test lock entities with auto-relock pulse duration."""
    lock_ped = AveVideo44Lock(mock_coordinator, device_id=9991, lock_id=1, name="Pedonale")
    lock_drv = AveVideo44Lock(mock_coordinator, device_id=9991, lock_id=2, name="Carraio")

    assert lock_ped.is_locked is True
    assert lock_drv.is_locked is True

    # Unlock pedestrian
    await lock_ped.async_unlock()
    mock_coordinator.api.unlock.assert_called_with(device_id="9991", lock_id="1")
    assert lock_ped.is_locked is False

    # Relock
    await lock_ped.async_lock()
    assert lock_ped.is_locked is True

    # Clean unload cancels timer
    await lock_ped.async_will_remove_from_hass()
    assert lock_ped._relock_task is None or lock_ped._relock_task.cancelled()


@pytest.mark.asyncio
async def test_button_entities(mock_coordinator):
    """Test unlock, intercom call, answer and hangup buttons."""
    btn_unlock1 = AveVideo44UnlockButton(mock_coordinator, device_id=9991, lock_id=1)
    btn_call = AveVideo44CallButton(mock_coordinator, device_id=9991)
    btn_ans = AveVideo44AnswerButton(mock_coordinator, device_id=9991)
    btn_hang = AveVideo44HangupButton(mock_coordinator, device_id=9991)

    await btn_unlock1.async_press()
    mock_coordinator.api.unlock.assert_called_with(device_id="9991", lock_id="1")

    mock_coordinator.async_call_intercom = AsyncMock()
    mock_coordinator.async_answer_call = AsyncMock()
    mock_coordinator.async_hangup_call = AsyncMock()

    await btn_call.async_press()
    mock_coordinator.async_call_intercom.assert_called_with("9991")

    await btn_ans.async_press()
    mock_coordinator.async_answer_call.assert_called_with("9991")

    await btn_hang.async_press()
    mock_coordinator.async_hangup_call.assert_called_with("9991")


@pytest.mark.asyncio
async def test_binary_sensor_entities(mock_coordinator):
    """Test incoming call sound sensor and online connectivity sensor."""
    sensor_call = AveVideo44IncomingCallBinarySensor(mock_coordinator, device_id=9991)
    sensor_online = AveVideo44OnlineBinarySensor(mock_coordinator, device_id=9991)

    assert sensor_call.is_on is False
    assert sensor_online.is_on is True

    # Trigger incoming call
    mock_coordinator.handle_incoming_call(caller_id="1-1-102", call_type="DEV_INDOORPHONE", device_id=9991)
    assert sensor_call.is_on is True


@pytest.mark.asyncio
async def test_event_entity(mock_coordinator):
    """Test doorbell event entity triggering for doorstation and intercom rings."""
    event_entity = AveVideo44DoorbellEvent(mock_coordinator, device_id=9991)
    event_entity._trigger_event = MagicMock()

    # Trigger doorstation ring
    mock_coordinator.handle_ring_event(device_id=9991, ring_type="doorstation_ring", caller_id="P1")
    event_entity.handle_coordinator_update()
    assert event_entity.event_types == ["doorstation_ring", "intercom_ring"]


@pytest.mark.asyncio
async def test_sensor_entities(mock_coordinator):
    """Test call status, caller name, and last call timestamp sensors."""
    s_status = AveVideo44CallStatusSensor(mock_coordinator, device_id=9991)
    s_caller = AveVideo44CallerNameSensor(mock_coordinator, device_id=9991)
    s_last = AveVideo44LastCallSensor(mock_coordinator, device_id=9991)

    assert s_status.native_value == "idle"
    assert s_caller.native_value == ""

    # Incoming call
    mock_coordinator.handle_incoming_call(caller_id="1-1-103", call_type="HOUSETOHOUSE", device_id=9991)
    assert s_status.native_value == "ringing"
    assert s_caller.native_value == "Cugino"
    assert s_last.native_value is not None


@pytest.mark.asyncio
async def test_select_entity(mock_coordinator):
    """Test intercom target select entity options from book."""
    select_entity = AveVideo44IntercomTargetSelect(mock_coordinator, device_id=9991)
    assert len(select_entity.options) == 3
    assert "1-1-101 (Piano Terra)" in select_entity.options

    await select_entity.async_select_option("1-1-103 (Cugino)")
    assert select_entity.current_option == "1-1-103 (Cugino)"
    assert select_entity.selected_room_code == "1-1-103"


@pytest.mark.asyncio
async def test_camera_entity(mock_coordinator):
    """Test RTSP camera entity and stream source generation."""
    cam = AveVideo44Camera(mock_coordinator, device_id=9991)

    # When device has IP configured in coordinator devices
    mock_coordinator.devices = [{"deviceId": 9991, "ip": "192.168.1.50"}]
    url = await cam.stream_source()
    assert url == "rtsp://192.168.1.50:554/live/sub"
    assert cam.supported_features == CameraEntityFeature.STREAM
    assert await cam.async_camera_image() == b"test_image"

    # When device has no IP (idle 2-wire camera)
    mock_coordinator.devices = [{"deviceId": 9991}]
    assert await cam.stream_source() is None
    assert cam.supported_features == CameraEntityFeature(0)
    assert await cam.async_camera_image() is None

    # When get_rtsp_url is explicitly mocked
    mock_coordinator.get_rtsp_url = MagicMock(return_value="rtsp://192.168.1.100:554/live/sub")
    assert await cam.stream_source() == "rtsp://192.168.1.100:554/live/sub"
    assert cam.supported_features == CameraEntityFeature.STREAM


@pytest.mark.asyncio
async def test_coordinator_get_rtsp_url(mock_coordinator):
    """Test coordinator.get_rtsp_url logic."""
    from custom_components.ave_video44.coordinator import AveVideo44Coordinator

    # When device has no IP, should return None (never 127.0.0.1)
    mock_coordinator.devices = [{"deviceId": "9991"}]
    mock_coordinator.active_device_id = None
    mock_coordinator.active_rtsp_url = None
    assert AveVideo44Coordinator.get_rtsp_url(mock_coordinator, "9991") is None

    # When device has IP configured
    mock_coordinator.devices = [{"deviceId": "9991", "ip": "192.168.1.50"}]
    assert AveVideo44Coordinator.get_rtsp_url(mock_coordinator, "9991") == "rtsp://192.168.1.50:554/live/sub"

    # When localhost is set, should return None
    mock_coordinator.devices = [{"deviceId": "9991", "ip": "127.0.0.1"}]
    assert AveVideo44Coordinator.get_rtsp_url(mock_coordinator, "9991") is None

    # When active_rtsp_url is set during active call
    mock_coordinator.devices = [{"deviceId": "9991"}]
    mock_coordinator.active_device_id = "9991"
    mock_coordinator.active_rtsp_url = "rtsp://live.stream/test"
    assert AveVideo44Coordinator.get_rtsp_url(mock_coordinator, "9991") == "rtsp://live.stream/test"


# --- WebSocket API Tests ---

@pytest.mark.asyncio
async def test_ws_call_control(mock_hass, mock_coordinator):
    """Test websocket ave_video44/call_control command."""
    mock_hass.data[DOMAIN] = {"entries": {mock_coordinator.entry_id: mock_coordinator}}
    conn = MagicMock()
    conn.send_result = MagicMock()
    conn.send_error = MagicMock()

    mock_coordinator.async_answer_call = AsyncMock()
    mock_coordinator.async_unlock = AsyncMock()

    msg = {
        "id": 1,
        "type": "ave_video44/call_control",
        "entry_id": mock_coordinator.entry_id,
        "device_id": 9991,
        "action": "answer",
    }

    await ws_api.ws_call_control(mock_hass, conn, msg)
    mock_coordinator.async_answer_call.assert_called_with(9991)
    conn.send_result.assert_called_with(1, {"success": True})

    # Test unlock without entry_id
    msg_unlock = {
        "id": 2,
        "type": "ave_video44/call_control",
        "device_id": 9991,
        "action": "unlock",
        "lock_id": "2",
    }
    await ws_api.ws_call_control(mock_hass, conn, msg_unlock)
    mock_coordinator.async_unlock.assert_called_with(9991, lock_id="2")
    conn.send_result.assert_called_with(2, {"success": True})


@pytest.mark.asyncio
async def test_ws_audio_tx(mock_hass, mock_coordinator):
    """Test websocket ave_video44/audio_tx transmitting base64 PCM16 frames."""
    mock_hass.data[DOMAIN] = {"entries": {mock_coordinator.entry_id: mock_coordinator}}
    conn = MagicMock()
    conn.send_result = MagicMock()

    # 160 samples PCM16 = 320 bytes
    pcm16_data = b"\x00\x01" * 160
    b64_payload = base64.b64encode(pcm16_data).decode("ascii")

    msg = {
        "id": 2,
        "type": "ave_video44/audio_tx",
        "entry_id": mock_coordinator.entry_id,
        "device_id": 9991,
        "payload": b64_payload,
    }

    await ws_api.ws_audio_tx(mock_hass, conn, msg)
    mock_coordinator.sip_session.send_pcm16_frame.assert_called_with(pcm16_data)
    conn.send_result.assert_called_with(2, {"success": True})


@pytest.mark.asyncio
async def test_ws_audio_subscribe_and_unsubscribe(mock_hass, mock_coordinator):
    """Test websocket ave_video44/audio_subscribe and unsubscribe callback."""
    mock_hass.data[DOMAIN] = {"entries": {mock_coordinator.entry_id: mock_coordinator}}
    conn = MagicMock()
    conn.send_result = MagicMock()
    conn.send_event = MagicMock()
    conn.subscriptions = {}

    msg = {
        "id": 42,
        "type": "ave_video44/audio_subscribe",
        "entry_id": mock_coordinator.entry_id,
        "device_id": 9991,
    }

    await ws_api.ws_audio_subscribe(mock_hass, conn, msg)
    assert 42 in conn.subscriptions

    # Invoke registered audio callback
    registered_cb = mock_coordinator.sip_session.add_rx_pcm16_callback.call_args[0][0]
    sample_rx = b"\x05\x05" * 160
    registered_cb(sample_rx)
    conn.send_event.assert_called()

    # Unsubscribe
    unsub = conn.subscriptions[42]
    unsub()
    mock_coordinator.sip_session.remove_rx_pcm16_callback.assert_called_once_with(registered_cb)


# --- Diagnostics Redaction Tests ---

def test_diagnostics_redact():
    """Test sensitive credentials redaction in diagnostics."""
    raw = {
        "account": "user@test.it",
        "email": "user@test.it",
        "password": "super_secret_password",
        "sessionId": "abc123456",
        "token": "tok_xyz",
        "sip_password": "sip_pass_val",
        "appSecret": "secret_key",
        "other": "normal_val",
        "nested": {
            "token": "nested_secret",
            "device": "PIT7WF",
        },
    }

    redacted = async_redact_data(raw)
    assert redacted["account"] == "**REDACTED**"
    assert redacted["email"] == "**REDACTED**"
    assert redacted["password"] == "**REDACTED**"
    assert redacted["sessionId"] == "**REDACTED**"
    assert redacted["token"] == "**REDACTED**"
    assert redacted["sip_password"] == "**REDACTED**"
    assert redacted["appSecret"] == "**REDACTED**"
    assert redacted["nested"]["token"] == "**REDACTED**"
    assert redacted["nested"]["device"] == "PIT7WF"
    assert redacted["other"] == "normal_val"


# --- v1.1.0 Entity Tests ---

def test_unlock_buttons_disabled_by_default(mock_coordinator):
    """Test AveVideo44UnlockButton has _attr_entity_registry_enabled_default is False while call buttons remain enabled."""
    unlock_1 = AveVideo44UnlockButton(mock_coordinator, 9991, lock_id=1)
    unlock_2 = AveVideo44UnlockButton(mock_coordinator, 9991, lock_id=2)
    assert unlock_1._attr_entity_registry_enabled_default is False
    assert unlock_2._attr_entity_registry_enabled_default is False

    call_btn = AveVideo44CallButton(mock_coordinator, 9991)
    answer_btn = AveVideo44AnswerButton(mock_coordinator, 9991)
    hangup_btn = AveVideo44HangupButton(mock_coordinator, 9991)
    assert getattr(call_btn, "_attr_entity_registry_enabled_default", True) is True
    assert getattr(answer_btn, "_attr_entity_registry_enabled_default", True) is True
    assert getattr(hangup_btn, "_attr_entity_registry_enabled_default", True) is True


@pytest.mark.asyncio
async def test_async_disable_duplicate_unlock_buttons(mock_hass, mock_entry):
    """Test _async_disable_duplicate_unlock_buttons disables unlock buttons if not already disabled."""
    import homeassistant.helpers.entity_registry as er
    from custom_components.ave_video44 import _async_disable_duplicate_unlock_buttons

    registry = er.EntityRegistry()
    mock_hass._entity_registry = registry

    # Add entries
    btn_ped = er.RegistryEntry("button.ped", f"{mock_entry.entry_id}_9991_btn_unlock_1", disabled_by=None)
    btn_gate = er.RegistryEntry("button.gate", f"{mock_entry.entry_id}_9991_btn_unlock_2", disabled_by=None)
    btn_call = er.RegistryEntry("button.call", f"{mock_entry.entry_id}_9991_btn_call", disabled_by=None)
    btn_user_dis = er.RegistryEntry("button.other", f"{mock_entry.entry_id}_9991_btn_unlock_1_other", disabled_by=er.RegistryEntryDisabler.USER)

    registry.entities = {
        "button.ped": btn_ped,
        "button.gate": btn_gate,
        "button.call": btn_call,
        "button.other": btn_user_dis,
    }

    await _async_disable_duplicate_unlock_buttons(mock_hass, mock_entry)

    assert btn_ped.disabled_by == er.RegistryEntryDisabler.INTEGRATION
    assert btn_gate.disabled_by == er.RegistryEntryDisabler.INTEGRATION
    assert btn_call.disabled_by is None
    assert btn_user_dis.disabled_by == er.RegistryEntryDisabler.USER


def test_intercom_target_select_options_and_selection(mock_coordinator):
    """Test AveVideo44IntercomTargetSelect default placeholder and dynamic options."""
    # When intercom_book is empty
    mock_coordinator.intercom_book = {}
    mock_coordinator.selected_intercom_targets = {}
    select = AveVideo44IntercomTargetSelect(mock_coordinator, 9991)

    assert select.options == ["Nessun interfono configurato"]
    assert select.current_option == "Nessun interfono configurato"
    assert select.selected_room_code == ""

    # When intercom_book is populated
    mock_coordinator.intercom_book = {"0101": "Interno 1", "0102": "Taverna"}
    select._init_options()
    assert select.options == ["0101 (Interno 1)", "0102 (Taverna)"]
    assert select.current_option == "0101 (Interno 1)"
    assert select.selected_room_code == "0101"


# --- v1.2.0 Camera Wake & Auto-Discovery Tests ---

@pytest.mark.asyncio
async def test_wake_camera_button(mock_coordinator):
    """Test AveVideo44WakeCameraButton entity properties and press action."""
    mock_coordinator.async_wake_camera = AsyncMock(return_value="rtsps://test.url")
    btn = AveVideo44WakeCameraButton(mock_coordinator, 9991)

    assert btn._attr_entity_registry_enabled_default is True
    assert "btn_wake_camera" in btn._attr_unique_id
    assert btn._attr_translation_key == "wake_camera"
    assert btn._attr_icon == "mdi:cctv"

    await btn.async_press()
    mock_coordinator.async_wake_camera.assert_called_once_with("9991")


@pytest.mark.asyncio
async def test_coordinator_async_wake_camera_and_hangup(mock_coordinator):
    """Test coordinator.async_wake_camera parses nested auth basic and ports, and hangup clears it."""
    mock_coordinator.api.control_monitoring = AsyncMock(return_value="833971686813601792")
    mock_coordinator.api.get_rtsp_config = AsyncMock(return_value={
        "auth": {
            "basic": {
                "username": "user!123",
                "password": "pwd@456",
            }
        },
        "serverEndpoints": [
            {
                "domain": "eu-video.gvs-icloud.com",
                "ports": "{\"rtsps\": 8322}",
            }
        ],
    })
    mock_coordinator.devices = [
        {"deviceId": "677771932745207808", "extraConfig": {"deviceNumber": "1", "deviceName": "Citofono"}}
    ]

    # 1. Wake camera
    url = await mock_coordinator.async_wake_camera("677771932745207808")
    assert mock_coordinator.api.control_monitoring.called
    assert mock_coordinator.call_state == "monitoring"
    assert mock_coordinator.active_device_id == "677771932745207808"
    assert url == "rtsps://user%21123:pwd%40456@eu-video.gvs-icloud.com:8322/stream/1/677771932745207808/0/1"
    assert mock_coordinator.active_rtsp_url == url
    assert mock_coordinator.get_rtsp_url("677771932745207808") == url
    assert "677771932745207808" not in mock_coordinator.user_hangup

    # 2. Hangup stops monitoring with action=3 and clears state
    await mock_coordinator.async_hangup_call("677771932745207808")
    assert mock_coordinator.api.control_monitoring.call_args[1]["action"] == 3
    assert mock_coordinator.active_rtsp_url is None
    assert mock_coordinator.call_state == "idle"
    assert mock_coordinator.get_rtsp_url("677771932745207808") is None
    assert "677771932745207808" in mock_coordinator.user_hangup


@pytest.mark.asyncio
async def test_coordinator_on_mqtt_event_monitoring(mock_coordinator):
    """Test coordinator._on_mqtt_event handles monitoring push notification and updates active_rtsp_url."""
    mock_coordinator._last_rtsp_auth = ("rtsps", "user%21123", "pwd%40456", "eu-video.gvs-icloud.com", 8322)
    mock_coordinator.active_rtsp_url = None
    mock_coordinator.call_state = "idle"

    event_payload = {
        "code": "monitoring",
        "action": 1,
        "value": {
            "result": {
                "serverUrl": "/stream/1/677771932745207808/0/1"
            }
        }
    }
    mock_coordinator._on_mqtt_event(event_payload)

    assert mock_coordinator.call_state == "monitoring"
    assert mock_coordinator.active_rtsp_url == "rtsps://user%21123:pwd%40456@eu-video.gvs-icloud.com:8322/stream/1/677771932745207808/0/1"


@pytest.mark.asyncio
async def test_camera_async_camera_image_ffmpeg(mock_coordinator):
    """Test AveVideo44Camera.async_camera_image returns None when idle and delegates to ffmpeg when active."""
    cam = AveVideo44Camera(mock_coordinator, device_id="677771932745207808")

    # Idle
    mock_coordinator.active_rtsp_url = None
    mock_coordinator.get_rtsp_url = MagicMock(return_value=None)
    assert await cam.async_camera_image() is None

    # Active stream source
    mock_coordinator.get_rtsp_url = MagicMock(return_value="rtsps://user:pwd@domain:8322/stream/1/677771932745207808/0/1")
    with patch("homeassistant.components.ffmpeg.async_get_image", AsyncMock(return_value=b"test_jpeg")) as mock_ffmpeg:
        img = await cam.async_camera_image(width=640, height=360)
        assert img == b"test_jpeg"
        mock_ffmpeg.assert_called_once_with(
            cam.hass,
            "rtsps://user:pwd@domain:8322/stream/1/677771932745207808/0/1",
            extra_cmd="-rtsp_transport tcp",
            width=640,
            height=360,
        )



@pytest.mark.asyncio
async def test_ws_call_control_monitor(mock_hass, mock_coordinator):
    """Test websocket ave_video44/call_control with action=monitor."""
    mock_hass.data[DOMAIN] = {"entries": {mock_coordinator.entry_id: mock_coordinator}}
    conn = MagicMock()
    conn.send_result = MagicMock()

    mock_coordinator.async_wake_camera = AsyncMock(return_value="rtsps://test_stream")

    msg = {
        "id": 88,
        "type": "ave_video44/call_control",
        "device_id": 9991,
        "action": "monitor",
    }
    await ws_api.ws_call_control(mock_hass, conn, msg)
    mock_coordinator.async_wake_camera.assert_called_once_with(9991)
    conn.send_result.assert_called_once()
    assert conn.send_result.call_args[0][0] == 88


@pytest.mark.asyncio
async def test_coordinator_intercom_auto_discovery(mock_coordinator):
    """Test coordinator.async_discover_intercoms discovers devices from extraConfig, deviceIntercomInfo and monitoring-list."""
    mock_coordinator.devices = [
        {
            "deviceId": "9991",
            "deviceName": "Posto Interno",
            "extraConfig": {"deviceNumber": "1", "deviceName": "Citofono"},
            "deviceIntercomInfo": [
                {"haZone": "1", "username": "0101", "deviceName": "Unità interna cloud due fili (TS-SMART)"}
            ],
        }
    ]
    mock_coordinator.api.get_monitoring_list = AsyncMock(return_value=[
        {"deviceNumber": "2", "name": "Posto Esterno 2"}
    ])

    discovered = await mock_coordinator.async_discover_intercoms()
    assert "1" in discovered
    assert discovered["1"] == "Citofono"
    assert "0101" in discovered
    assert "Zona 1" in discovered["0101"] or "TS-SMART" in discovered["0101"]
    assert "2" in discovered
    assert discovered["2"] == "Posto Esterno 2"


