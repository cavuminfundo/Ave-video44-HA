"""Tests for AVE Video V44 core protocol and REST API."""

import base64
import hashlib
import hmac
import pytest
from unittest.mock import AsyncMock, MagicMock

from custom_components.ave_video44.const import (
    MAGIC_HEADER,
    COMMON_PORT,
    AUDIO_PORT,
    ENTRANCEGUARD_FUNCTION,
    COM_REMOTE_UNLOCK_ASK,
    COM_REMOTE_UNLOCK_REPLY,
    DEV_DOORSTATION,
    DEV_INDOORPHONE,
    DEFAULT_APP_SECRET,
)
from custom_components.ave_video44.core.protocol import (
    compute_gvs_sign,
    hash_password_sha256,
    build_gvs_udp_packet,
    parse_gvs_udp_packet,
    pcm16_to_alaw,
    alaw_to_pcm16,
)
from custom_components.ave_video44.core.api import AveCloudApi


def test_compute_gvs_sign_filtering_and_determinism():
    """Verify sign calculation ignores 'sign' and None, sorts keys and returns lowercase base64."""
    params = {
        "device_id": "dev123",
        "lockId": "1",
        "sign": "to_be_ignored",
        "empty_val": None,
        "action": "unlock",
    }
    secret = "secret_key"
    # Query string should be "action=unlock&device_id=dev123&lockId=1"
    expected_qs = "action=unlock&device_id=dev123&lockId=1"
    expected_mac = hmac.new(
        secret.encode("utf-8"),
        expected_qs.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    expected_sign = base64.b64encode(expected_mac).decode("utf-8").lower()

    calculated_sign = compute_gvs_sign(params, secret=secret)
    assert calculated_sign == expected_sign
    assert calculated_sign.islower()


def test_hash_password_sha256():
    """Verify password hashing returns lowercase sha256 hex."""
    pwd = "secretPassword123!"
    expected = hashlib.sha256(pwd.encode("utf-8")).hexdigest().lower()
    assert hash_password_sha256(pwd) == expected


def test_gvs_udp_packet_roundtrip_and_reply_flag():
    """Verify building and parsing GVS binary UDP packets with 10-byte header."""
    src_addr = bytes([1, 1, 1, 1, 0, 0])
    dst_addr = bytes([1, 1, 1, 2, 0, 0])
    data = b"\x01\x02\x03\x04"

    # Test ASK packet
    packet = build_gvs_udp_packet(
        func_code=ENTRANCEGUARD_FUNCTION,
        cmd_code=COM_REMOTE_UNLOCK_ASK,
        src_dev_type=DEV_INDOORPHONE,
        src_room=src_addr,
        dst_dev_type=DEV_DOORSTATION,
        dst_room=dst_addr,
        data=data,
    )

    assert packet.startswith(MAGIC_HEADER)
    assert len(packet) >= 12 + 16 + len(data)

    parsed = parse_gvs_udp_packet(packet)
    assert parsed["func_code"] == ENTRANCEGUARD_FUNCTION
    assert parsed["cmd_code"] == COM_REMOTE_UNLOCK_ASK
    assert parsed["src_dev_type"] == DEV_INDOORPHONE
    assert parsed["src_room"] == src_addr
    assert parsed["dst_dev_type"] == DEV_DOORSTATION
    assert parsed["dst_room"] == dst_addr
    assert parsed["data"] == data

    # Test REPLY packet (0x80 | ASK)
    expected_reply_cmd = 0x80 | COM_REMOTE_UNLOCK_ASK
    assert expected_reply_cmd == COM_REMOTE_UNLOCK_REPLY

    reply_packet = build_gvs_udp_packet(
        func_code=ENTRANCEGUARD_FUNCTION,
        cmd_code=expected_reply_cmd,
        src_dev_type=DEV_DOORSTATION,
        src_room=dst_addr,
        dst_dev_type=DEV_INDOORPHONE,
        dst_room=src_addr,
        data=b"\x00",
    )
    parsed_reply = parse_gvs_udp_packet(reply_packet)
    assert parsed_reply["cmd_code"] == COM_REMOTE_UNLOCK_REPLY
    assert parsed_reply["is_reply"] is True


def test_parse_gvs_udp_packet_invalid_header():
    """Verify parsing raises ValueError on invalid magic header or short packets."""
    with pytest.raises(ValueError, match="Invalid magic header"):
        parse_gvs_udp_packet(b"INVALIDHDR\x00\x00\x00")

    with pytest.raises(ValueError, match="Packet too short"):
        parse_gvs_udp_packet(MAGIC_HEADER[:5])


def test_pcm16_and_alaw_pure_python_lookup_tables():
    """Verify pure-Python PCMA (G.711a) <-> PCM16 conversion without audioop."""
    # 160 16-bit samples = 320 bytes (20ms at 8kHz)
    pcm_samples = []
    for i in range(160):
        # Generate varied 16-bit values across positive and negative range
        val = int(32767 * ((i % 20) - 10) / 10)
        pcm_samples.append(val.to_bytes(2, byteorder="little", signed=True))
    pcm16_data = b"".join(pcm_samples)
    assert len(pcm16_data) == 320

    # Encode to ALAW
    alaw_data = pcm16_to_alaw(pcm16_data)
    assert len(alaw_data) == 160

    # Decode back to PCM16
    decoded_pcm16 = alaw_to_pcm16(alaw_data)
    assert len(decoded_pcm16) == 320

    # Roundtrip check: G.711 A-law is 8-bit companded, so verify fidelity within quantization tolerance
    for i in range(160):
        orig_val = int.from_bytes(pcm16_data[i * 2 : i * 2 + 2], byteorder="little", signed=True)
        dec_val = int.from_bytes(decoded_pcm16[i * 2 : i * 2 + 2], byteorder="little", signed=True)
        # Quantization error for A-law is bounded
        assert abs(orig_val - dec_val) <= max(64, abs(orig_val) * 0.1)


@pytest.mark.asyncio
async def test_ave_cloud_api_login_with_password():
    """Verify AveCloudApi.login_with_password performs SHA-256 and HMAC-SHA1 signature."""
    session = MagicMock()
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={"code": 0, "data": {"token": "tok_123", "sessionId": "sess_456"}})
    session.post = MagicMock(return_value=mock_resp)
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=None)

    api = AveCloudApi(session=session)
    res = await api.login_with_password("user@example.com", "mySecret123")

    assert res["token"] == "tok_123"
    assert res["sessionId"] == "sess_456"
    assert api.token == "tok_123"
    assert api.session_id == "sess_456"

    # Check payload sent
    call_args = session.post.call_args
    assert "/usercenter/api/uc/loginToGvs/account" in call_args[0][0]
    payload = call_args[1]["json"]
    assert payload["account"] == "user@example.com"
    assert payload["password"] == hashlib.sha256(b"mySecret123").hexdigest().lower()
    assert payload["channel"] == "App"
    assert "sign" in payload
    assert "ts" in payload


@pytest.mark.asyncio
async def test_ave_cloud_api_otp_flow():
    """Verify AveCloudApi OTP request and login."""
    session = MagicMock()
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(return_value={"code": 0, "data": {"token": "otp_tok", "sessionId": "otp_sess"}})
    session.post = MagicMock(return_value=mock_resp)
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=None)

    api = AveCloudApi(session=session)
    req_res = await api.request_otp("user@example.com")
    assert req_res["code"] == 0

    login_res = await api.login_with_otp("user@example.com", "123456")
    assert login_res["token"] == "otp_tok"
    assert login_res["sessionId"] == "otp_sess"


@pytest.mark.asyncio
async def test_ave_cloud_api_get_devices_unlock_and_configs():
    """Verify AveCloudApi get_devices, unlock, get_sip_account and get_rtsp_config."""
    session = MagicMock()
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(
        return_value={
            "code": 0,
            "data": [
                {
                    "deviceId": "dev_001",
                    "deviceNumber": "1-1-1-1",
                    "deviceName": "Doorstation 1",
                    "devType": 50,
                }
            ],
        }
    )
    session.get = MagicMock(return_value=mock_resp)
    session.post = MagicMock(return_value=mock_resp)
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=None)

    api = AveCloudApi(session=session, token="test_token", session_id="test_sess")

    # get_devices
    devices = await api.get_devices(home_id="home_123")
    assert len(devices) == 1
    assert devices[0]["deviceId"] == "dev_001"

    # unlock
    mock_resp.json = AsyncMock(return_value={"code": 0, "msg": "success"})
    unlock_res = await api.unlock(device_id="dev_001", lock_id="1")
    assert unlock_res["code"] == 0

    # get_sip_account
    mock_resp.json = AsyncMock(
        return_value={
            "code": 0,
            "data": {
                "username": "sip_user",
                "password": "sip_password",
                "serverUrl": "open-sips.gvs-icloud.com",
            },
        }
    )
    sip_info = await api.get_sip_account(device_id="dev_001")
    assert sip_info["username"] == "sip_user"

    # get_rtsp_config
    mock_resp.json = AsyncMock(
        return_value={
            "code": 0,
            "data": {
                "mainStreamUrl": "rtsp://open-sips.gvs-icloud.com:554/live/main",
                "subStreamUrl": "rtsp://open-sips.gvs-icloud.com:554/live/sub",
            },
        }
    )
    rtsp_info = await api.get_rtsp_config(device_id="dev_001")
    assert "mainStreamUrl" in rtsp_info
