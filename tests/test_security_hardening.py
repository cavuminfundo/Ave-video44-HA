"""Comprehensive security hardening tests for AVE Video V44 backend."""

import base64
from unittest.mock import AsyncMock, MagicMock

import pytest
import voluptuous as vol
from homeassistant.components import websocket_api

from custom_components.ave_video44 import (
    DOMAIN,
    SERVICE_CALL_ACTION_SCHEMA,
    SERVICE_CALL_INTERCOM_SCHEMA,
    SERVICE_UNLOCK_SCHEMA,
    _async_register_services,
)
from custom_components.ave_video44 import (
    websocket_api as ws_api,
)
from custom_components.ave_video44.core.protocol import (
    MAGIC_HEADER,
    parse_gvs_udp_packet,
)
from custom_components.ave_video44.core.sip_session import (
    MAX_SIP_CONTENT_LENGTH,
    MAX_SIP_HEADER_BYTES,
    AveSipSession,
    CloudSipMediaSession,
    _sanitize_device_id,
)


def test_parse_gvs_udp_packet_rejects_short_header_payload():
    """Verify packets with payload_length < 16 raise ValueError instead of IndexError."""
    # payload_length = 2 (total packet length = 14 bytes >= 12 + 2, but < 28 bytes needed for header fields)
    malformed = MAGIC_HEADER + b"\x00\x02\x01\x01"
    with pytest.raises(ValueError, match="Truncated GVS header payload"):
        parse_gvs_udp_packet(malformed)


def test_service_schemas_validate_inputs_and_register_with_schema():
    """Verify domain services enforce Voluptuous schemas on registration and validation."""
    valid_unlock = SERVICE_UNLOCK_SCHEMA({"device_id": "9991", "lock_id": 2})
    assert valid_unlock["lock_id"] == "2"

    with pytest.raises(vol.Invalid):
        SERVICE_UNLOCK_SCHEMA({"device_id": "9991", "lock_id": "99; rm -rf /"})

    with pytest.raises(vol.Invalid):
        SERVICE_CALL_INTERCOM_SCHEMA({"device_id": "9991", "room_code": "X" * 64})

    valid_action = SERVICE_CALL_ACTION_SCHEMA({"device_id": "9991"})
    assert valid_action["device_id"] == "9991"

    hass = MagicMock()
    hass.services.has_service = MagicMock(return_value=False)
    hass.services.async_register = MagicMock()
    _async_register_services(hass)

    assert hass.services.async_register.call_count == 4
    for call in hass.services.async_register.call_args_list:
        assert "schema" in call.kwargs and call.kwargs["schema"] is not None


def test_redact_rtsp_url_edge_cases():
    """Verify _redact_rtsp_url masks user:pass across diverse URL schemes and handles non-strings."""
    assert ws_api._redact_rtsp_url(None) is None
    assert ws_api._redact_rtsp_url("") == ""
    assert ws_api._redact_rtsp_url(12345) == 12345
    assert (
        ws_api._redact_rtsp_url("rtsp://admin:secret123@192.168.1.100:554/ch0")
        == "rtsp://***:***@192.168.1.100:554/ch0"
    )
    assert (
        ws_api._redact_rtsp_url("rtsps://user:p%40ss@cloud.ave.it:8554/stream")
        == "rtsps://***:***@cloud.ave.it:8554/stream"
    )
    assert (
        ws_api._redact_rtsp_url("rtsp://192.168.1.100:554/ch0")
        == "rtsp://192.168.1.100:554/ch0"
    )


@pytest.mark.asyncio
async def test_ws_call_control_monitor_redacts_rtsp_credentials():
    """Verify action=monitor never leaks plaintext RTSP username/password to WebSocket clients."""
    hass = MagicMock()
    coord = MagicMock()
    coord.entry_id = "entry1"
    coord.devices = [{"deviceId": 9991}]
    coord.async_wake_camera = AsyncMock(
        return_value="rtsps://ave_user:SuperSecretPwd123@stream.ave.it:8554/live/ch1"
    )
    hass.data = {DOMAIN: {"entries": {"entry1": coord}}}
    conn = MagicMock()

    await ws_api.ws_call_control(
        hass,
        conn,
        {"id": 10, "type": "ave_video44/call_control", "device_id": 9991, "action": "monitor"},
    )
    conn.send_result.assert_called_once()
    result_payload = conn.send_result.call_args[0][1]
    assert "SuperSecretPwd123" not in result_payload["rtsp_url"]
    assert "ave_user" not in result_payload["rtsp_url"]
    assert result_payload["rtsp_url"] == "rtsps://***:***@stream.ave.it:8554/live/ch1"


@pytest.mark.asyncio
async def test_ws_audio_tx_payload_bounds():
    """Verify ws_audio_tx rejects oversized base64 payload and excessive decoded PCM16 bytes."""
    hass = MagicMock()
    coord = MagicMock()
    coord.entry_id = "entry1"
    coord.devices = [{"deviceId": 9991}]
    session = MagicMock()
    session.is_active = True
    coord.cloud_sip_sessions = {"9991": session}
    hass.data = {DOMAIN: {"entries": {"entry1": coord}}}
    conn = MagicMock()

    # 1. Base64 payload exceeding MAX_AUDIO_TX_B64_LEN
    oversized_b64 = "A" * (ws_api.MAX_AUDIO_TX_B64_LEN + 10)
    with pytest.raises(websocket_api.WebSocketError) as exc_info:
        await ws_api.ws_audio_tx(
            hass,
            conn,
            {"id": 1, "type": "ave_video44/audio_tx", "device_id": "9991", "payload": oversized_b64, "ack": True},
        )
    assert "invalid_format" in str(exc_info.value.args)

    # 2. Decoded PCM16 exceeding MAX_AUDIO_TX_PCM_BYTES
    huge_pcm = b"\x00" * (ws_api.MAX_AUDIO_TX_PCM_BYTES + 100)
    huge_b64 = base64.b64encode(huge_pcm).decode("ascii")
    with pytest.raises(websocket_api.WebSocketError) as exc_info:
        await ws_api.ws_audio_tx(
            hass,
            conn,
            {"id": 2, "type": "ave_video44/audio_tx", "device_id": "9991", "payload": huge_b64, "ack": True},
        )
    assert "invalid_format" in str(exc_info.value.args)


@pytest.mark.asyncio
async def test_ws_audio_tx_rate_limit_and_session_cap():
    """Verify ws_audio_tx enforces session cap (<=32) and drops frames exceeding rate limit."""
    ws_api._AUDIO_TX_SESSIONS.clear()
    hass = MagicMock()
    coord = MagicMock()
    coord.entry_id = "entry1"
    coord.devices = [{"deviceId": 9991}]
    session = MagicMock()
    session.is_active = True
    coord.cloud_sip_sessions = {"9991": session}
    hass.data = {DOMAIN: {"entries": {"entry1": coord}}}
    conn = MagicMock()

    small_frame = base64.b64encode(b"\x00\x00" * 160).decode("ascii")

    # Flood with 40 distinct device_ids to verify hard cap of 32 sessions
    for i in range(40):
        dev_id = f"dev_{i}"
        coord.cloud_sip_sessions[dev_id] = session
        await ws_api.ws_audio_tx(
            hass,
            conn,
            {"id": i + 1, "type": "ave_video44/audio_tx", "device_id": dev_id, "payload": small_frame},
        )
    assert len(ws_api._AUDIO_TX_SESSIONS) <= ws_api.MAX_AUDIO_TX_SESSIONS

    # Flood a single session beyond MAX_AUDIO_TX_FPS within the same second
    session.send_pcm16_frame.reset_mock()
    for i in range(ws_api.MAX_AUDIO_TX_FPS + 25):
        await ws_api.ws_audio_tx(
            hass,
            conn,
            {
                "id": 100 + i,
                "type": "ave_video44/audio_tx",
                "device_id": "9991",
                "payload": small_frame,
                "ack": True,
            },
        )
    assert session.send_pcm16_frame.call_count == ws_api.MAX_AUDIO_TX_FPS
    assert conn.send_error.call_count == 25
    assert conn.send_error.call_args[0][1] == "rate_limited"


@pytest.mark.asyncio
async def test_read_sip_msg_rejects_oversized_header_and_content_length():
    """Verify _read_sip_msg prevents OOM on unbounded headers or huge Content-Length."""
    sess = CloudSipMediaSession(sip_config={}, device_id="9991")
    sess._reader = AsyncMock()

    # 1. Header exceeding MAX_SIP_HEADER_BYTES without \r\n\r\n
    sess._reader.read = AsyncMock(return_value=b"A" * (MAX_SIP_HEADER_BYTES + 1024))
    with pytest.raises(ValueError, match="SIP header exceeds maximum"):
        await sess._read_sip_msg()
    assert len(sess._rx_buf) == 0

    # 2. Content-Length exceeding MAX_SIP_CONTENT_LENGTH
    oversized_cl = MAX_SIP_CONTENT_LENGTH + 100
    raw_msg = (
        f"INVITE sip:101@domain SIP/2.0\r\nContent-Length: {oversized_cl}\r\n\r\n".encode()
    )
    sess._reader.read = AsyncMock(return_value=raw_msg)
    with pytest.raises(ValueError, match="Invalid or excessive SIP Content-Length"):
        await sess._read_sip_msg()
    assert len(sess._rx_buf) == 0

    # 3. Negative Content-Length
    raw_neg = b"INVITE sip:101@domain SIP/2.0\r\nContent-Length: -5\r\n\r\n"
    sess._reader.read = AsyncMock(return_value=raw_neg)
    with pytest.raises(ValueError, match="Invalid or excessive SIP Content-Length"):
        await sess._read_sip_msg()
    assert len(sess._rx_buf) == 0


def test_udp_source_ip_filtering_prevents_spoofing_and_rtp_hijack():
    """Verify CloudSipMediaSession._process_inbound_audio_socket and AveSipSession reject UDP packets from untrusted LAN IPs."""
    sess = CloudSipMediaSession(
        sip_config={"server": "198.51.100.10:5061"},
        device_id="9991",
    )
    sess._audio_proto = "RTP/AVP"
    sess._remote_ip = "198.51.100.20"
    sess._remote_audio_port = 12000

    rtp_pcma = b"\x80\x08\x00\x01\x00\x00\x00\xa0\x12\x34\x56\x78" + (b"\xd5" * 160)

    # Inbound audio socket: rogue LAN IP 192.168.1.250 must be dropped
    mock_sock = MagicMock()
    mock_sock.recvfrom = MagicMock(
        side_effect=[
            (rtp_pcma, ("192.168.1.250", 31337)),
            BlockingIOError(),
        ]
    )
    sess._audio_sock = mock_sock
    sess._process_inbound_audio_socket()
    assert sess._remote_audio_port == 12000
    assert sess._audio_rx_pkts == 0

    # Legitimate packet from 198.51.100.20 is accepted and updates port if NAT rebinds
    mock_sock.recvfrom = MagicMock(
        side_effect=[
            (rtp_pcma, ("198.51.100.20", 12002)),
            BlockingIOError(),
        ]
    )
    sess._process_inbound_audio_socket()
    assert sess._remote_audio_port == 12002
    assert sess._audio_rx_pkts == 1

    # AveSipSession LAN filter
    lan_sess = AveSipSession(local_host="192.168.1.10", local_port=5060, remote_ip="192.168.1.50")
    lan_sess.handle_rtp_packet = MagicMock()

    # Spoofed packet from rogue LAN host 192.168.1.99 must be ignored
    lan_sess.datagram_received(rtp_pcma, ("192.168.1.99", 8302))
    lan_sess.handle_rtp_packet.assert_not_called()

    # Legitimate packet from configured remote_ip 192.168.1.50 is processed
    lan_sess.datagram_received(rtp_pcma, ("192.168.1.50", 8302))
    lan_sess.handle_rtp_packet.assert_called_once_with(rtp_pcma)


def test_cloud_sip_media_session_is_trusted_udp_source():
    """Verify _is_trusted_udp_source recognizes loopback, remote_ip, and sip_config domains."""
    sess = CloudSipMediaSession(
        sip_config={"server": "sip.ave-cloud.it:5061", "proxy": "198.51.100.5"},
        device_id="9991",
    )
    sess._remote_ip = "198.51.100.20"

    assert sess._is_trusted_udp_source(("127.0.0.1", 1234)) is True
    assert sess._is_trusted_udp_source(("::1", 1234)) is True
    assert sess._is_trusted_udp_source(("0.0.0.0", 1234)) is True
    assert sess._is_trusted_udp_source(("198.51.100.20", 5000)) is True
    assert sess._is_trusted_udp_source(("sip.ave-cloud.it", 5061)) is True
    assert sess._is_trusted_udp_source(("198.51.100.5", 5061)) is True
    assert sess._is_trusted_udp_source(("192.168.1.200", 5000)) is False
    assert sess._is_trusted_udp_source(None) is False
    assert sess._is_trusted_udp_source("not_a_tuple") is False


def test_sdp_temp_path_sanitizes_device_id():
    """Verify CloudSipMediaSession sanitizes device_id against path traversal sequences."""
    assert _sanitize_device_id("../../etc/passwd") == "etcpasswd"
    assert _sanitize_device_id("dev_99-1") == "dev_99-1"
    assert _sanitize_device_id("../../../") == "unknown"
    assert _sanitize_device_id(None) == "unknown"

    sess = CloudSipMediaSession(sip_config={}, device_id="../../etc/passwd")
    assert sess.device_id == "etcpasswd"
