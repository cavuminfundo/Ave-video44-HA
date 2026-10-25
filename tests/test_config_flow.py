"""Tests for AVE Video V44 config flow and options flow."""

import sys
from types import ModuleType
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

# Ensure Home Assistant stubs exist if running in environment without homeassistant core
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

    # core
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

    # config_entries
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

    # const
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

    # exceptions
    class HomeAssistantError(Exception): pass
    class ConfigEntryNotReady(HomeAssistantError): pass
    class ConfigEntryAuthFailed(HomeAssistantError): pass
    exceptions_mod.HomeAssistantError = HomeAssistantError
    exceptions_mod.ConfigEntryNotReady = ConfigEntryNotReady
    exceptions_mod.ConfigEntryAuthFailed = ConfigEntryAuthFailed

    # helpers
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
            for listener in self._listeners:
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

    # components
    class LockEntity(Entity): pass
    class ButtonEntity(Entity): pass
    class BinarySensorDeviceClass:
        SOUND = "sound"
        CONNECTIVITY = "connectivity"
    class BinarySensorEntity(Entity): pass
    class EventDeviceClass:
        DOORBELL = "doorbell"
    class EventEntity(Entity):
        def _trigger_event(self, event_type, event_data=None): pass
    class SensorEntity(Entity): pass
    class SelectEntity(Entity): pass
    class CameraEntityFeature:
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

    class StaticPathConfig:
        def __init__(self, path, url_path, cache_headers=True):
            self.path = path
            self.url_path = url_path
            self.cache_headers = cache_headers
    http_mod.StaticPathConfig = StaticPathConfig

    device_registry_mod = ModuleType("homeassistant.helpers.device_registry")
    device_registry_mod.DeviceInfo = DeviceInfo

    # Register into sys.modules
    stubs = {
        "homeassistant": ha_mod,
        "homeassistant.core": core_mod,
        "homeassistant.config_entries": config_entries_mod,
        "homeassistant.const": const_mod,
        "homeassistant.exceptions": exceptions_mod,
        "homeassistant.helpers": helpers_mod,
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
    }
    for name, mod in stubs.items():
        sys.modules[name] = mod

_ensure_ha_stubs()

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
    sys.modules["voluptuous"] = vol_mod
    import voluptuous as vol

from custom_components.ave_video44.const import (
    CONF_ACCOUNT,
    CONF_AUTH_METHOD,
    CONF_INTERCOM_BOOK,
    CONF_OTP,
    CONF_PASSWORD,
    CONF_PREFERRED_VIDEO_STREAM,
    CONF_UNLOCK_PULSE_DURATION,
    DOMAIN,
)
from custom_components.ave_video44.config_flow import (
    AveVideo44ConfigFlow,
    AveVideo44OptionsFlow,
)


@pytest.mark.asyncio
async def test_flow_user_init_shows_auth_selection():
    """Test user step shows authentication choice."""
    flow = AveVideo44ConfigFlow()
    flow.hass = MagicMock()

    result = await flow.async_step_user()
    assert result["type"] == "form"
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_flow_user_password_success():
    """Test successful password login flow."""
    flow = AveVideo44ConfigFlow()
    flow.hass = MagicMock()

    with patch("custom_components.ave_video44.config_flow.AveCloudApi") as mock_api_cls:
        mock_api = mock_api_cls.return_value
        mock_api.async_close = AsyncMock()
        mock_api.login_with_password = AsyncMock(return_value={"userId": 1234, "sessionId": "sess_1", "token": "tok_1"})
        mock_api.get_homes = AsyncMock(return_value=[{"homeId": 101, "homeName": "Casa"}])
        mock_api.get_home_list = AsyncMock(return_value=[{"homeId": 101, "homeName": "Casa"}])
        mock_api.get_devices = AsyncMock(return_value=[])

        # Step user chooses password
        res_step_user = await flow.async_step_user({CONF_AUTH_METHOD: "password"})
        assert res_step_user["type"] == "form"
        assert res_step_user["step_id"] == "password"

        # Step password submit
        result = await flow.async_step_password({
            CONF_ACCOUNT: "test@example.com",
            CONF_PASSWORD: "secret_password",
        })

        assert result["type"] == "create_entry"
        assert result["title"] == "test@example.com (Casa)"
        assert result["data"][CONF_ACCOUNT] == "test@example.com"
        assert result["data"]["home_id"] == 101


@pytest.mark.asyncio
async def test_flow_user_password_invalid_auth():
    """Test password login error handling."""
    flow = AveVideo44ConfigFlow()
    flow.hass = MagicMock()

    with patch("custom_components.ave_video44.config_flow.AveCloudApi") as mock_api_cls:
        mock_api = mock_api_cls.return_value
        mock_api.async_close = AsyncMock()
        mock_api.login_with_password = AsyncMock(side_effect=Exception("Invalid credentials"))

        result = await flow.async_step_password({
            CONF_ACCOUNT: "test@example.com",
            CONF_PASSWORD: "wrong_password",
        })

        assert result["type"] == "form"
        assert result["errors"]["base"] == "invalid_auth"


@pytest.mark.asyncio
async def test_flow_user_password_empty_tokens_triggers_invalid_auth():
    """Verify missing tokens trigger invalid_auth error."""
    flow = AveVideo44ConfigFlow()
    flow.hass = MagicMock()

    with patch("custom_components.ave_video44.config_flow.AveCloudApi") as mock_api_cls:
        mock_api = mock_api_cls.return_value
        mock_api.async_close = AsyncMock()
        mock_api.login_with_password = AsyncMock(return_value={"userId": 1234})

        result = await flow.async_step_password({
            CONF_ACCOUNT: "test@example.com",
            CONF_PASSWORD: "secret_password",
        })

        assert result["type"] == "form"
        assert result["errors"]["base"] == "invalid_auth"


@pytest.mark.asyncio
async def test_flow_otp_success():
    """Test successful OTP login flow."""
    flow = AveVideo44ConfigFlow()
    flow.hass = MagicMock()

    with patch("custom_components.ave_video44.config_flow.AveCloudApi") as mock_api_cls:
        mock_api = mock_api_cls.return_value
        mock_api.async_close = AsyncMock()
        mock_api.request_otp = AsyncMock(return_value=True)
        mock_api.login_with_otp = AsyncMock(return_value={"userId": 5678, "sessionId": "sess_otp", "token": "tok_otp"})
        mock_api.get_homes = AsyncMock(return_value=[{"homeId": 202, "homeName": "Villa"}])
        mock_api.get_home_list = AsyncMock(return_value=[{"homeId": 202, "homeName": "Villa"}])
        mock_api.get_devices = AsyncMock(return_value=[])

        # 1. Select OTP
        res1 = await flow.async_step_user({CONF_AUTH_METHOD: "otp"})
        assert res1["step_id"] == "otp_request"

        # 2. Request OTP
        res2 = await flow.async_step_otp_request({CONF_ACCOUNT: "+393331234567"})
        assert res2["step_id"] == "otp_verify"

        # 3. Verify OTP
        res3 = await flow.async_step_otp_verify({CONF_OTP: "123456"})
        assert res3["type"] == "create_entry"
        assert res3["title"] == "+393331234567 (Villa)"
        assert res3["data"]["home_id"] == 202


@pytest.mark.asyncio
async def test_options_flow_update():
    """Test options flow configuration of intercom book and pulse."""
    from homeassistant.config_entries import ConfigEntry
    entry = ConfigEntry(
        entry_id="entry_123",
        data={CONF_ACCOUNT: "test@example.com"},
        options={
            CONF_INTERCOM_BOOK: "1-1-101=Piano Terra",
            CONF_UNLOCK_PULSE_DURATION: 2,
            CONF_PREFERRED_VIDEO_STREAM: "sub_stream",
        },
    )
    flow = AveVideo44OptionsFlow(entry)

    # Initial show form
    res_form = await flow.async_step_init()
    assert res_form["type"] == "form"

    # Save new options
    res_save = await flow.async_step_init({
        CONF_INTERCOM_BOOK: "1-1-101=Piano Terra, 1-1-102=Primo Piano, 1-1-103=Cugino",
        CONF_UNLOCK_PULSE_DURATION: 3,
        CONF_PREFERRED_VIDEO_STREAM: "main_stream",
    })
    assert res_save["type"] == "create_entry"
    assert "1-1-103=Cugino" in res_save["data"][CONF_INTERCOM_BOOK]
    assert res_save["data"][CONF_UNLOCK_PULSE_DURATION] == 3


def test_options_flow_read_only_base_property():
    """Verify AveVideo44OptionsFlow works when base class has read-only config_entry property."""
    class ReadOnlyBaseOptionsFlow:
        @property
        def config_entry(self):
            raise AttributeError("can't set attribute 'config_entry'")

    class TestOptionsFlow(AveVideo44OptionsFlow, ReadOnlyBaseOptionsFlow):
        pass

    entry = MagicMock()
    flow = TestOptionsFlow(entry)
    assert flow.config_entry == entry
