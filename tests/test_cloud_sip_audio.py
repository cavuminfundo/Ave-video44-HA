"""Tests for Cloud SIP Media Session Audio RX/TX, SRTP packetization, and G.711 codec."""

import asyncio
import os
import stat
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.ave_video44.core.sip_session import CloudSipMediaSession


def test_parse_200_ok_sdp_audio_crypto():
    """Verify parse_200_ok_sdp extracts audio payload type and audio crypto suite/key."""
    sample_sdp = (
        "v=0\r\n"
        "o=- 123 123 IN IP4 192.168.1.50\r\n"
        "s=Session\r\n"
        "c=IN IP4 192.168.1.50\r\n"
        "t=0 0\r\n"
        "m=audio 10004 RTP/SAVP 0\r\n"
        "a=rtpmap:0 PCMU/8000\r\n"
        "a=crypto:1 AES_CM_128_HMAC_SHA1_80 inline:YXVkaW9rZXkxMjM0NTY3ODkwMTIzNDU2Nzg5MDE=\r\n"
        "m=video 10006 RTP/SAVP 96\r\n"
        "a=rtpmap:96 H264/90000\r\n"
        "a=crypto:1 AES_CM_128_HMAC_SHA1_80 inline:dmlkZW9rZXkxMjM0NTY3ODkwMTIzNDU2Nzg5MDE=\r\n"
    )
    parsed = CloudSipMediaSession.parse_200_ok_sdp(sample_sdp)
    assert parsed["remote_audio_port"] == 10004
    assert str(parsed["audio_payload_type"]) == "0"
    assert parsed.get("callee_audio_suite") == "AES_CM_128_HMAC_SHA1_80"
    assert parsed.get("callee_audio_key") == "YXVkaW9rZXkxMjM0NTY3ODkwMTIzNDU2Nzg5MDE="


def test_cloud_sip_media_session_generate_audio_sdp():
    """Verify _generate_audio_sdp formats valid SDP for FFmpeg audio listener."""
    session = CloudSipMediaSession(
        device_id="101",
        sip_username="sip:test@domain.com",
        sip_password="dummy_password",
        target_sip_uri="sip:target@domain.com",
    )
    sdp_text = session._generate_audio_sdp(
        ffmpeg_audio_port=12344,
        crypto_suite="AES_CM_128_HMAC_SHA1_80",
        crypto_key="YXVkaW9rZXkxMjM0NTY3ODkwMTIzNDU2Nzg5MDE=",
        payload_type=0,
    )
    assert "m=audio 12344 RTP/SAVP 0" in sdp_text
    assert "a=rtpmap:0 PCMU/8000" in sdp_text
    assert "a=crypto:1 AES_CM_128_HMAC_SHA1_80 inline:YXVkaW9rZXkxMjM0NTY3ODkwMTIzNDU2Nzg5MDE=" in sdp_text


@pytest.mark.asyncio
async def test_cloud_sip_media_session_audio_rx_readexactly_and_incomplete():
    """Verify stdout reader loop uses readexactly(320) and handles IncompleteReadError gracefully."""
    session = CloudSipMediaSession(
        device_id="101",
        sip_username="sip:test@domain.com",
        sip_password="dummy_password",
        target_sip_uri="sip:target@domain.com",
    )
    received_frames = []

    def on_pcm(data: bytes):
        received_frames.append(data)

    session.add_rx_pcm16_callback(on_pcm)
    assert on_pcm in session._rx_pcm16_callbacks
    assert not hasattr(session, "set_rx_pcm16_callback")

    # 20ms G.711 frame decoded to 160 linear 16-bit mono samples (320 bytes)
    fake_frame = b"\x12\x34" * 160
    mock_stdout = AsyncMock()
    mock_stdout.readexactly = AsyncMock(
        side_effect=[fake_frame, asyncio.IncompleteReadError(partial=b"\x12", expected=320)]
    )

    mock_proc = MagicMock()
    mock_proc.stdout = mock_stdout
    session._ffmpeg_audio_proc = mock_proc
    session.is_active = True

    await session._ffmpeg_audio_stdout_loop()

    assert len(received_frames) == 1
    assert received_frames[0] == fake_frame

    session.remove_rx_pcm16_callback(on_pcm)
    assert on_pcm not in session._rx_pcm16_callbacks


@pytest.mark.asyncio
async def test_cloud_sip_media_session_write_sdp_non_blocking_permissions(tmp_path):
    """Verify SDP audio file is written asynchronously with 0o600 permissions."""
    session = CloudSipMediaSession(
        device_id="101",
        sip_username="sip:test@domain.com",
        sip_password="dummy_password",
        target_sip_uri="sip:target@domain.com",
    )
    target_path = str(tmp_path / "test_audio.sdp")
    sdp_content = "v=0\r\ntest"

    await session._async_write_sdp_file(target_path, sdp_content)
    assert os.path.exists(target_path)
    file_stat = os.stat(target_path)
    assert stat.S_IMODE(file_stat.st_mode) == 0o600

    await session._async_remove_sdp_file(target_path)
    assert not os.path.exists(target_path)


@pytest.mark.asyncio
async def test_cloud_sip_media_session_audio_relay_isolation():
    """Verify audio loopback sendto errors do not crash UDP relay loop or video processing."""
    session = CloudSipMediaSession(
        device_id="101",
        sip_username="sip:test@domain.com",
        sip_password="dummy_password",
        target_sip_uri="sip:target@domain.com",
    )
    session.is_active = True
    session._ffmpeg_audio_port = 19999
    session._audio_sock = MagicMock()
    # First call returns packet, second raises BlockingIOError to break while
    session._audio_sock.recvfrom.side_effect = [(b"fake_srtp_pkt", ("192.168.1.1", 10000)), BlockingIOError()]
    # Force sendto to fail on loopback
    session._audio_sock.sendto.side_effect = OSError("Connection refused")

    session._process_inbound_audio_socket()

    assert session._audio_rx_pkts == 1
    assert session.is_active is True


def test_cloud_sip_media_session_rms_telemetry():
    """Verify compute_pcm16_rms_dbfs calculates accurate dBFS values."""
    session = CloudSipMediaSession(
        device_id="101",
        sip_username="sip:test@domain.com",
        sip_password="dummy_password",
        target_sip_uri="sip:target@domain.com",
    )
    silence = b"\x00\x00" * 160
    assert session.compute_pcm16_rms_dbfs(silence) <= -90.0

    full_scale = b"\xff\x7f" * 160
    assert -0.5 <= session.compute_pcm16_rms_dbfs(full_scale) <= 0.0


@pytest.mark.asyncio
async def test_cloud_sip_media_session_kill_switch_disabled():
    """Verify enable_audio=False skips FFmpeg audio subprocess and SDP generation."""
    session = CloudSipMediaSession(
        device_id="101",
        sip_username="sip:test@domain.com",
        sip_password="dummy_password",
        target_sip_uri="sip:target@domain.com",
        enable_audio=False,
    )
    assert session.enable_audio is False
    assert session._ffmpeg_audio_proc is None


def test_protocol_g711_ulaw_encoding():
    """Verify pcm16_to_ulaw converts 16-bit linear PCM to G.711u (PCMU)."""
    from custom_components.ave_video44.core.protocol import pcm16_to_ulaw, ulaw_to_pcm16
    pcm_in = b"\x00\x00\xff\x7f\x00\x80"
    ulaw = pcm16_to_ulaw(pcm_in)
    assert len(ulaw) == 3
    pcm_out = ulaw_to_pcm16(ulaw)
    assert len(pcm_out) == 6


def test_cloud_sip_media_session_send_pcm16_frame_srtp():
    """Verify send_pcm16_frame constructs valid RTP header, encrypts with SRTP and sends to socket."""
    session = CloudSipMediaSession(
        device_id="101",
        sip_username="sip:test@domain.com",
        sip_password="dummy_password",
        target_sip_uri="sip:target@domain.com",
    )
    session.is_active = True
    session._remote_ip = "192.168.1.100"
    session._remote_audio_port = 10008
    session._audio_payload_type = 0
    session._srtp_tx_audio_key = b"A" * 30
    session._audio_sock = MagicMock()

    pcm_frame = b"\x00\x01" * 160
    session.send_pcm16_frame(pcm_frame)

    session._audio_sock.sendto.assert_called_once()
    packet, target = session._audio_sock.sendto.call_args[0]
    assert target == ("192.168.1.100", 10008)
    assert len(packet) == 182
    assert packet[0] == 0x80
    assert session._tx_seq == 1
    assert session._tx_timestamp == 160


def test_cloud_sip_media_session_tx_rms_telemetry():
    """Verify send_pcm16_frame computes TX RMS telemetry and maintains a bounded queue of 10 frames."""
    session = CloudSipMediaSession(
        device_id="101",
        sip_username="sip:test@domain.com",
        sip_password="dummy_password",
        target_sip_uri="sip:target@domain.com",
    )
    session.is_active = True
    session._remote_ip = "192.168.1.100"
    session._remote_audio_port = 10008
    session._audio_payload_type = 0
    session._srtp_tx_audio_key = b"A" * 30
    session._audio_sock = MagicMock()

    frame = b"\x00\x01" * 160
    for _ in range(15):
        session.send_pcm16_frame(frame)

    assert len(session._audio_tx_rms_samples) == 15
    assert len(session._tx_audio_queue) == 10


def test_cloud_sip_media_session_tx_disabled_when_kill_switch_active():
    """Verify send_pcm16_frame does not send datagrams when enable_audio=False."""
    session = CloudSipMediaSession(
        device_id="101",
        sip_username="sip:test@domain.com",
        sip_password="dummy_password",
        target_sip_uri="sip:target@domain.com",
        enable_audio=False,
    )
    session.is_active = True
    session._remote_ip = "192.168.1.100"
    session._remote_audio_port = 10008
    session._audio_sock = MagicMock()

    frame = b"\x00\x01" * 160
    session.send_pcm16_frame(frame)

    session._audio_sock.sendto.assert_not_called()


def test_cloud_sip_media_session_generate_audio_sdp_plain_rtp():
    """Verify _generate_audio_sdp emits RTP/AVP without a=crypto when crypto_key is empty."""
    session = CloudSipMediaSession(
        device_id="101",
        sip_username="sip:test@domain.com",
        sip_password="dummy_password",
        target_sip_uri="sip:target@domain.com",
    )
    sdp_text = session._generate_audio_sdp(
        ffmpeg_audio_port=12344,
        crypto_suite="",
        crypto_key="",
        payload_type=0,
    )
    assert "m=audio 12344 RTP/AVP 0" in sdp_text
    assert "a=crypto:" not in sdp_text
    assert "a=rtpmap:0 PCMU/8000" in sdp_text


@pytest.mark.asyncio
async def test_cloud_sip_media_session_audio_keepalive_payload_type():
    """Verify _udp_relay_loop does not transmit H.264 video RTP packets on the remote audio socket."""
    session = CloudSipMediaSession(
        device_id="101",
        sip_username="sip:test@domain.com",
        sip_password="dummy_password",
        target_sip_uri="sip:target@domain.com",
    )
    session.is_active = True
    session._audio_payload_type = 0
    mock_audio_sock = MagicMock()
    session._audio_sock = mock_audio_sock
    session._video_sock = None
    session._rtcp_sock = None

    relay_task = asyncio.create_task(
        session._udp_relay_loop("192.168.1.50", 10006, 10004)
    )
    await asyncio.sleep(0.01)
    session.is_active = False
    await relay_task

    sent_audio_packets = [call[0][0] for call in mock_audio_sock.sendto.call_args_list]
    assert len(sent_audio_packets) > 0
    for packet in sent_audio_packets:
        payload_type = packet[1] & 0x7F
        assert payload_type != 96, "Audio keepalive must not use H.264 video payload type (96)"
        assert payload_type in (0, 8, 13), f"Expected audio payload type, got {payload_type}"


@pytest.mark.asyncio
async def test_cloud_sip_media_session_ffmpeg_audio_spawn_plain_rtp():
    """Verify async_start spawns FFmpeg audio subprocess when callee_audio_key is empty or absent."""
    session = CloudSipMediaSession(
        device_id="101",
        sip_username="sip:test@domain.com",
        sip_password="dummy_password",
        target_sip_uri="sip:target@domain.com",
        enable_audio=True,
    )
    sdp_200 = (
        "v=0\r\n"
        "c=IN IP4 51.144.180.20\r\n"
        "m=audio 25000 RTP/AVP 0\r\n"
        "a=rtpmap:0 PCMU/8000\r\n"
        "m=video 25002 RTP/SAVP 96\r\n"
        "a=rtpmap:96 H264/90000\r\n"
        "a=crypto:1 AES_CM_128_HMAC_SHA1_80 inline:cmVtb3RldmlkZW9rZXkxMjM0NTY3ODkwMTIzNDU2\r\n"
    )
    sip_responses = [
        ("SIP/2.0 200 OK", {"content-length": "0"}, ""),
        ("SIP/2.0 200 OK", {"content-length": str(len(sdp_200)), "contact": "<sip:target@domain.com>"}, sdp_200),
    ]

    async def _mock_read_sip_msg():
        return sip_responses.pop(0)

    session._read_sip_msg = _mock_read_sip_msg

    mock_reader = AsyncMock()
    mock_writer = MagicMock()
    mock_writer.write = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_writer.wait_closed = AsyncMock()

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)), \
         patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec, \
         patch.object(session, "wait_for_first_frame", return_value=b"frame"):
        fake_proc = MagicMock()
        fake_proc.stdout = AsyncMock()
        fake_proc.stdout.read = AsyncMock(return_value=b"")
        fake_proc.stdout.readexactly = AsyncMock(
            side_effect=asyncio.IncompleteReadError(partial=b"", expected=320)
        )
        fake_proc.wait = AsyncMock(return_value=0)
        mock_exec.return_value = fake_proc

        started = await session.async_start()
        assert started is True
        assert session._ffmpeg_audio_proc is not None
        await session.async_stop()


@pytest.mark.asyncio
async def test_cloud_sip_media_session_mjpeg_high_quality_qscale():
    """Verify async_start uses -q:v 2 for crisp JPEG definition and sharp edge quality."""
    session = CloudSipMediaSession(
        device_id="101",
        sip_username="sip:test@domain.com",
        sip_password="dummy_password",
        target_sip_uri="sip:target@domain.com",
    )
    sdp_200 = (
        "v=0\r\n"
        "c=IN IP4 51.144.180.20\r\n"
        "m=audio 25000 RTP/SAVP 0\r\n"
        "m=video 25002 RTP/SAVP 96\r\n"
        "a=rtpmap:96 H264/90000\r\n"
        "a=crypto:1 AES_CM_128_HMAC_SHA1_80 inline:cmVtb3RldmlkZW9rZXkxMjM0NTY3ODkwMTIzNDU2\r\n"
    )
    sip_responses = [
        ("SIP/2.0 200 OK", {"content-length": "0"}, ""),
        ("SIP/2.0 200 OK", {"content-length": str(len(sdp_200)), "contact": "<sip:target@domain.com>"}, sdp_200),
    ]

    async def _mock_read_sip_msg():
        return sip_responses.pop(0)

    session._read_sip_msg = _mock_read_sip_msg

    mock_reader = AsyncMock()
    mock_writer = MagicMock()
    mock_writer.write = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_writer.wait_closed = AsyncMock()

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)), \
         patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec, \
         patch.object(session, "wait_for_first_frame", return_value=b"frame"):
        fake_proc = MagicMock()
        fake_proc.stdout = AsyncMock()
        fake_proc.stdout.read = AsyncMock(return_value=b"")
        fake_proc.stdout.readexactly = AsyncMock(
            side_effect=asyncio.IncompleteReadError(partial=b"", expected=320)
        )
        fake_proc.wait = AsyncMock(return_value=0)
        mock_exec.return_value = fake_proc

        started = await session.async_start()
        assert started is True

        video_cmd_args = None
        for call_item in mock_exec.call_args_list:
            args = call_item[0]
            if "-q:v" in args:
                video_cmd_args = args
                break

        assert video_cmd_args is not None
        qv_idx = video_cmd_args.index("-q:v")
        assert video_cmd_args[qv_idx + 1] == "2"
        await session.async_stop()


@pytest.mark.asyncio
async def test_coordinator_commit_session_preserves_rx_callbacks(mock_coordinator):
    """Verify async_commit_session transfers registered audio RX callbacks from old to new session."""
    callback_fn = MagicMock()
    old_sess = MagicMock()
    old_sess._rx_pcm16_callbacks = {callback_fn}
    old_sess.async_stop = AsyncMock()

    mock_coordinator.cloud_sip_sessions["101"] = old_sess

    new_sess = MagicMock()
    new_sess.is_active = False
    new_sess.add_rx_pcm16_callback = MagicMock()

    await mock_coordinator.async_commit_session("101", new_sess)

    new_sess.add_rx_pcm16_callback.assert_called_with(callback_fn)


@pytest.mark.asyncio
async def test_coordinator_wake_camera_requests_hd_resolution(mock_coordinator):
    """Verify async_wake_camera requests HD stream (resolution_level=1) from cloud monitoring API."""
    mock_coordinator.api.control_monitoring = AsyncMock(return_value="call123")
    mock_coordinator.api.get_rtsp_config = AsyncMock(return_value={})
    mock_coordinator.devices = [
        {"deviceId": "101", "extraConfig": {"deviceNumber": "1"}}
    ]

    await mock_coordinator.async_wake_camera("101")

    mock_coordinator.api.control_monitoring.assert_called_once()
    call_kwargs = mock_coordinator.api.control_monitoring.call_args[1]
    assert call_kwargs.get("resolution_level") == 1


def test_srtp_rfc3711_key_derivation_vectors():
    """Verify RFC 3711 Appendix B.3 key derivation vectors for AES-128-CM PRF."""
    from custom_components.ave_video44.core.sip_session import (
        _derive_srtp_session_keys,
        _encrypt_srtp_packet,
    )
    import hashlib
    import hmac

    master_key = bytes.fromhex("E1F97A0D3E018BE0D64FA32C06DE4139")
    master_salt = bytes.fromhex("0EC675AD498AFEEBB6960B3AABE6")
    raw_key = master_key + master_salt

    k_e, k_a, k_s = _derive_srtp_session_keys(raw_key)
    assert k_e == bytes.fromhex("C61E7A93744F39EE10734AFE3FF7A087")
    assert k_a == bytes.fromhex("CEBE321F6FF7716B6FD4AB49AF256A156D38BAA4")
    assert k_s == bytes.fromhex("30CBBC08863D8C85D49DB34A9AE1")

    rtp_header = bytes([0x80, 0x08, 0x00, 0x01, 0x00, 0x00, 0x00, 0xA0, 0x12, 0x34, 0x56, 0x78])
    rtp_payload = b"\xd5" * 160
    srtp_pkt = _encrypt_srtp_packet(rtp_header + rtp_payload, raw_key, ssrc=0x12345678, seq=1, roc=0)
    expected_tag = hmac.new(k_a, srtp_pkt[:-10] + (0).to_bytes(4, "big"), hashlib.sha1).digest()[:10]
    assert srtp_pkt[-10:] == expected_tag

    srtp_pkt_inferred = _encrypt_srtp_packet(rtp_header + rtp_payload, raw_key, roc=0)
    assert srtp_pkt_inferred == srtp_pkt




