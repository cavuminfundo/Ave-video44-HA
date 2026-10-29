"""Tests for AveVideo44Coordinator call control, wake camera triggers, and session management."""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_coordinator_answer_call_wakes_camera_when_no_active_session(mock_coordinator):
    """Verify async_answer_call invokes async_wake_camera when device has no active Cloud SIP session."""
    mock_coordinator.async_wake_camera = AsyncMock()
    mock_coordinator.async_update_listeners = MagicMock()
    mock_coordinator.cloud_sip_sessions.clear()

    await mock_coordinator.async_answer_call("9991")

    mock_coordinator.async_wake_camera.assert_awaited_once_with("9991")
    assert mock_coordinator.call_state == "in_call"
    assert mock_coordinator.active_device_id == "9991"
    mock_coordinator.async_update_listeners.assert_called_once()


@pytest.mark.asyncio
async def test_coordinator_answer_call_device_id_resolution(mock_coordinator):
    """Verify async_answer_call resolves active_device_id or first device when device_id is None."""
    mock_coordinator.async_wake_camera = AsyncMock()
    mock_coordinator.async_update_listeners = MagicMock()
    mock_coordinator.cloud_sip_sessions.clear()

    # Case 1: device_id=None, active_device_id is set
    mock_coordinator.active_device_id = "8888"
    await mock_coordinator.async_answer_call(None)
    mock_coordinator.async_wake_camera.assert_awaited_with("8888")

    # Case 2: device_id=None, active_device_id=None -> falls back to first device in mock_coordinator.devices ("9991")
    mock_coordinator.async_wake_camera.reset_mock()
    mock_coordinator.active_device_id = None
    await mock_coordinator.async_answer_call(None)
    mock_coordinator.async_wake_camera.assert_awaited_with("9991")
    assert mock_coordinator.active_device_id == "9991"


@pytest.mark.asyncio
async def test_coordinator_answer_call_skips_wake_if_session_already_active(mock_coordinator):
    """Verify async_answer_call does not call async_wake_camera if CloudSipMediaSession is already active."""
    mock_coordinator.async_wake_camera = AsyncMock()
    mock_coordinator.async_update_listeners = MagicMock()
    active_session = MagicMock()
    active_session.is_active = True
    mock_coordinator.cloud_sip_sessions["9991"] = active_session

    await mock_coordinator.async_answer_call("9991")

    mock_coordinator.async_wake_camera.assert_not_called()
    assert mock_coordinator.call_state == "in_call"
    assert mock_coordinator.active_device_id == "9991"
