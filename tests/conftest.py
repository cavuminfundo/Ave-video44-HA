"""Common fixtures for AVE Video V44 tests."""

import asyncio
import sys
from types import ModuleType
from typing import Any
from unittest.mock import AsyncMock, MagicMock
import pytest


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
