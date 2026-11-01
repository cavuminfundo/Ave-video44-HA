"""Tests for static brand assets and HACS update entity icon override."""

from unittest.mock import AsyncMock, MagicMock

import pytest

try:
    from homeassistant.const import EVENT_STATE_CHANGED
except (ImportError, AttributeError):
    EVENT_STATE_CHANGED = "state_changed"

from custom_components.ave_video44 import (
    _BRAND_ICON_URL,
    DOMAIN,
    _async_override_hacs_update_icon,
    _async_register_card,
)


@pytest.mark.asyncio
async def test_async_register_brand_static_paths():
    """Verify brand static paths (icon and logo) are registered with cache_headers=True."""
    hass = MagicMock()
    hass.data = {DOMAIN: {}}
    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()

    assert _BRAND_ICON_URL == "/ave_video44_brand/icon.png"

    await _async_register_card(hass)

    hass.http.async_register_static_paths.assert_awaited_once()
    registered_configs = hass.http.async_register_static_paths.call_args[0][0]

    urls = {cfg.url_path: cfg for cfg in registered_configs}
    assert "/ave_video44_brand/icon.png" in urls
    assert "/ave_video44_brand/logo.png" in urls
    assert urls["/ave_video44_brand/icon.png"].cache_headers is True
    assert urls["/ave_video44_brand/logo.png"].cache_headers is True


def test_override_hacs_update_icon_customize_and_existing_state():
    """Verify customize dict is populated and existing state icon is overridden."""
    hass = MagicMock()
    hass.data = {}
    hass.bus = MagicMock()
    hass.states = MagicMock()

    # Pre-existing state with default HACS brands URL
    old_state = MagicMock()
    old_state.state = "on"
    old_state.attributes = {
        "title": "AVE Video V44",
        "entity_picture": "https://brands.home-assistant.io/_/ave_video44/icon.png",
    }
    hass.states.get.return_value = old_state

    _async_override_hacs_update_icon(hass)

    # 1. customize dict check
    assert "homeassistant_customize" in hass.data
    customize = hass.data["homeassistant_customize"]
    assert "update.ave_video_v44_update" in customize
    assert customize["update.ave_video_v44_update"]["entity_picture"] == _BRAND_ICON_URL

    # 2. immediate state update check
    hass.states.async_set.assert_called_once()
    call_args = hass.states.async_set.call_args[0]
    assert call_args[0] == "update.ave_video_v44_update"
    assert call_args[1] == "on"
    assert call_args[2]["entity_picture"] == _BRAND_ICON_URL
    assert call_args[2]["title"] == "AVE Video V44"


def test_override_hacs_update_icon_event_listener():
    """Verify EVENT_STATE_CHANGED listener overrides icon dynamically and avoids loops."""
    hass = MagicMock()
    hass.data = {}
    hass.bus = MagicMock()
    hass.states = MagicMock()
    hass.states.get.return_value = None

    listener = None

    def capture_listener(event_type, callback):
        nonlocal listener
        if event_type == EVENT_STATE_CHANGED:
            listener = callback

    hass.bus.async_listen.side_effect = capture_listener

    _async_override_hacs_update_icon(hass)

    assert listener is not None
    assert hass.data[DOMAIN]["hacs_icon_listener_registered"] is True

    # Calling again should not re-register listener
    hass.bus.async_listen.reset_mock()
    _async_override_hacs_update_icon(hass)
    hass.bus.async_listen.assert_not_called()

    # 1. Event for different entity: ignored
    event_other = MagicMock()
    event_other.data = {
        "entity_id": "sensor.other",
        "new_state": MagicMock(attributes={"entity_picture": "old"}),
    }
    listener(event_other)
    hass.states.async_set.assert_not_called()

    # 2. Event for update entity with different icon: updated
    new_state = MagicMock()
    new_state.state = "off"
    new_state.attributes = {
        "title": "AVE Video V44",
        "entity_picture": "https://brands.home-assistant.io/_/ave_video44/icon.png",
    }
    event_target = MagicMock()
    event_target.data = {
        "entity_id": "update.ave_video_v44_update",
        "new_state": new_state,
    }
    listener(event_target)
    hass.states.async_set.assert_called_once()
    args = hass.states.async_set.call_args[0]
    assert args[0] == "update.ave_video_v44_update"
    assert args[1] == "off"
    assert args[2]["entity_picture"] == _BRAND_ICON_URL

    # 3. Event where icon is already _BRAND_ICON_URL: no loop / no extra call
    hass.states.async_set.reset_mock()
    new_state_ok = MagicMock()
    new_state_ok.state = "off"
    new_state_ok.attributes = {"entity_picture": _BRAND_ICON_URL}
    event_ok = MagicMock()
    event_ok.data = {
        "entity_id": "update.ave_video_v44_update",
        "new_state": new_state_ok,
    }
    listener(event_ok)
    hass.states.async_set.assert_not_called()
