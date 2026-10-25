"""Common fixtures for AVE Video V44 tests."""

import asyncio
import sys
from types import ModuleType
from typing import Any
from unittest.mock import AsyncMock, MagicMock
import pytest


# Voluptuous stub if not present
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
        sys.modules[name] = mod

_ensure_ha_stubs()


@pytest.fixture
def mock_aiohttp_session():
    """Return a mock aiohttp ClientSession."""
    session = MagicMock()
    session.post = MagicMock()
    session.get = MagicMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def mock_hass():
    from homeassistant.core import HomeAssistant
    hass = HomeAssistant()
    hass.bus.async_fire = MagicMock()
    hass.services.async_register = MagicMock()
    hass.loop = MagicMock()
    hass.loop.call_soon_threadsafe = lambda func, *args: func(*args)
    return hass


@pytest.fixture
def mock_entry():
    from homeassistant.config_entries import ConfigEntry
    from custom_components.ave_video44.const import (
        CONF_ACCOUNT,
        CONF_INTERCOM_BOOK,
        CONF_PASSWORD,
        CONF_UNLOCK_PULSE_DURATION,
    )
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
    from custom_components.ave_video44.coordinator import AveVideo44Coordinator
    coord = AveVideo44Coordinator(mock_hass, mock_entry)
    coord.api = MagicMock()
    coord.api.unlock = AsyncMock(return_value=True)
    coord.api.control_monitoring = AsyncMock(return_value=123)
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
