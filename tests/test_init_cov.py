"""Tests for initialization, static card registration, and entry reloading in AVE Video V44."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ave_video44 import (
    _CARD_VERSION,
    DOMAIN,
    _async_register_card,
    async_reload_entry,
    async_setup_entry,
    async_unload_entry,
)


@pytest.mark.asyncio
async def test_async_register_card_caching_and_version():
    """Verify card registration disables card HTTP caching and uses version 1.3.8."""
    fake_resources = MagicMock()
    fake_resources.loaded = True
    fake_resources.async_items = MagicMock(return_value=[])
    fake_resources.async_create_item = AsyncMock()
    fake_lovelace = MagicMock()
    fake_lovelace.resources = fake_resources

    hass = MagicMock()
    hass.data = {DOMAIN: {}, "lovelace": fake_lovelace}
    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()

    assert _CARD_VERSION == "1.3.9"

    await _async_register_card(hass)

    hass.http.async_register_static_paths.assert_awaited_once()
    registered_configs = hass.http.async_register_static_paths.call_args[0][0]
    assert len(registered_configs) in (2, 4)
    for cfg in registered_configs:
        if cfg.url_path in ("/ave_video44_card/ave-video44-card.js", "/ave_video44_frontend/ave-video44-card.js"):
            assert cfg.cache_headers is False
        elif cfg.url_path in ("/ave_video44_brand/icon.png", "/ave_video44_brand/logo.png"):
            assert cfg.cache_headers is True

    fake_resources.async_create_item.assert_awaited_once()
    registered_item = fake_resources.async_create_item.call_args[0][0]
    assert "?v=1.3.9" in registered_item["url"]
    assert registered_item["url"] == "/ave_video44_card/ave-video44-card.js?v=1.3.9"


@pytest.mark.asyncio
async def test_async_reload_entry_skips_reload_when_only_data_updated():
    """Verify async_reload_entry avoids reload on data-only update but reloads on options change."""
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "test_entry_123"
    entry.data = {"token": "token_initial", "session_id": "sess_1"}
    entry.options = {"enable_sidebar_panel": True}

    coordinator = MagicMock()
    coordinator.update_intercom_book = MagicMock()
    entry.runtime_data = coordinator

    hass.data = {
        DOMAIN: {
            "entries": {entry.entry_id: coordinator},
            "entry_options": {entry.entry_id: dict(entry.options)},
        }
    }
    hass.config_entries = MagicMock()
    hass.config_entries.async_reload = AsyncMock()

    with patch(
        "custom_components.ave_video44._async_sync_sidebar_dashboard",
        new_callable=AsyncMock,
    ) as mock_sync:
        # Case 1: only data updated (e.g. token renewal in coordinator), options unchanged
        entry.data = {"token": "token_renewed", "session_id": "sess_2"}
        await async_reload_entry(hass, entry)

        mock_sync.assert_awaited_once_with(hass, entry)
        coordinator.update_intercom_book.assert_called_once()
        hass.config_entries.async_reload.assert_not_called()
        assert hass.data[DOMAIN]["entry_options"][entry.entry_id] == {
            "enable_sidebar_panel": True
        }

        # Case 2: options modified by user
        mock_sync.reset_mock()
        coordinator.update_intercom_book.reset_mock()
        entry.options = {"enable_sidebar_panel": False}

        await async_reload_entry(hass, entry)

        mock_sync.assert_awaited_once_with(hass, entry)
        coordinator.update_intercom_book.assert_called_once()
        hass.config_entries.async_reload.assert_awaited_once_with(entry.entry_id)
        assert hass.data[DOMAIN]["entry_options"][entry.entry_id] == {
            "enable_sidebar_panel": False
        }


@pytest.mark.asyncio
async def test_async_setup_and_unload_entry_tracks_options():
    """Verify async_setup_entry records options and async_unload_entry clears them."""
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "test_entry_options_track"
    entry.data = {"host": "192.168.1.100"}
    entry.options = {"enable_sidebar_panel": True}
    entry.add_update_listener = MagicMock()
    entry.async_on_unload = MagicMock()

    hass.data = {}
    hass.config_entries = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

    with (
        patch("custom_components.ave_video44.AveVideo44Coordinator") as mock_coord_cls,
        patch(
            "custom_components.ave_video44._async_register_card", new_callable=AsyncMock
        ),
        patch(
            "custom_components.ave_video44._async_disable_duplicate_unlock_buttons",
            new_callable=AsyncMock,
        ),
        patch(
            "custom_components.ave_video44._async_sync_sidebar_dashboard",
            new_callable=AsyncMock,
        ),
        patch("custom_components.ave_video44._async_register_services"),
    ):
        mock_coord = MagicMock()
        mock_coord.async_config_entry_first_refresh = AsyncMock()
        mock_coord.async_start = AsyncMock()
        mock_coord.async_shutdown = AsyncMock()
        mock_coord_cls.return_value = mock_coord

        setup_ok = await async_setup_entry(hass, entry)
        assert setup_ok is True
        assert hass.data[DOMAIN]["entry_options"][entry.entry_id] == {
            "enable_sidebar_panel": True
        }

        unload_ok = await async_unload_entry(hass, entry)
        assert unload_ok is True
        assert entry.entry_id not in hass.data[DOMAIN]["entry_options"]
