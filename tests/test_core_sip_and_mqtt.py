"""Tests for AVE Video V44 MQTT listener and SIP session."""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.ave_video44.const import (
    DEV_DOORSTATION,
    DEV_INDOORPHONE,
    AUDIO_PORT,
)
from custom_components.ave_video44.core.mqtt import AveMqttListener
from custom_components.ave_video44.core.sip_session import AveSipSession


@pytest.mark.asyncio
async def test_ave_mqtt_listener_lifecycle_and_dispatch():
    """Verify AveMqttListener non-blocking start, message routing and stop."""
    events_received = []

    def on_event(event_type: str, data: dict):
        events_received.append((event_type, data))

    listener = AveMqttListener(
        session_id="mock_session_123",
        broker_host="eu.emqx.gvs-icloud.com",
        broker_port=8883,
        device_ids=["dev_monitor_1", "dev_doorstation_1"],
        on_event=on_event,
    )

    with patch.object(listener, "_create_client") as mock_client_factory:
        mock_paho = MagicMock()
        mock_client_factory.return_value = mock_paho

        await listener.async_start()
        assert listener.is_running is True
        mock_paho.connect_async.assert_called_once()
        mock_paho.loop_start.assert_called_once()

        # Simulate incoming MQTT message: call in
        call_in_payload = json.dumps({
            "code": "monitoring",
            "action": 1,
            "senderName": "Portone Principale",
            "senderId": "dev_doorstation_1",
            "outDoorNum": "1-1-1-1",
            "targetId": "dev_monitor_1",
        }).encode("utf-8")

        listener._on_message(
            None,
            None,
            MagicMock(topic="smarthome/device/dev_doorstation_1", payload=call_in_payload),
        )

        assert len(events_received) == 1
        ev_type, ev_data = events_received[0]
        assert ev_type == "call_incoming"
        assert ev_data["senderName"] == "Portone Principale"

        # Simulate incoming MQTT message: unlock confirmation
        unlock_payload = json.dumps({
            "code": "unlock",
            "action": 1,
            "deviceId": "dev_doorstation_1",
            "lockId": "1",
        }).encode("utf-8")

        listener._on_message(
            None,
            None,
            MagicMock(topic="smarthome/device/dev_doorstation_1", payload=unlock_payload),
        )

        assert len(events_received) == 2
        assert events_received[1][0] == "unlock"

        # Stop
        await listener.async_stop()
        assert listener.is_running is False
        mock_paho.loop_stop.assert_called_once()
        mock_paho.disconnect.assert_called_once()


def test_sip_invite_parsing_doorstation_vs_indoorphone():
    """Verify parsing SIP INVITE identifies DEV_DOORSTATION vs DEV_INDOORPHONE."""
    # Doorstation INVITE
    doorstation_invite = (
        b"INVITE sip:1001@192.168.1.55:5060 SIP/2.0\r\n"
        b"Via: SIP/2.0/UDP 192.168.1.100:5060;branch=z9hG4bK-1\r\n"
        b"From: <sip:DOORSTATION_001@192.168.1.100>;tag=1234\r\n"
        b"To: <sip:1001@192.168.1.55>\r\n"
        b"Call-ID: call-12345@192.168.1.100\r\n"
        b"CSeq: 1 INVITE\r\n"
        b"Contact: <sip:DOORSTATION_001@192.168.1.100:5060>\r\n"
        b"devType: 50\r\n"
        b"Content-Type: application/sdp\r\n"
        b"Content-Length: 0\r\n\r\n"
    )

    parsed_door = AveSipSession.parse_sip_message(doorstation_invite)
    assert parsed_door["method"] == "INVITE"
    assert parsed_door["dev_type"] == DEV_DOORSTATION
    assert parsed_door["call_id"] == "call-12345@192.168.1.100"

    # Indoorphone INVITE (IS)
    indoor_invite = (
        b"INVITE sip:1-1-102@192.168.1.55:5060 SIP/2.0\r\n"
        b"Via: SIP/2.0/UDP 192.168.1.87:5060;branch=z9hG4bK-2\r\n"
        b"From: <sip:IS_1-1-101@192.168.1.87>;tag=5678\r\n"
        b"To: <sip:1-1-102@192.168.1.55>\r\n"
        b"Call-ID: call-67890@192.168.1.87\r\n"
        b"CSeq: 1 INVITE\r\n"
        b"targetType: HOUSETOHOUSE\r\n"
        b"devType: 97\r\n\r\n"
    )

    parsed_indoor = AveSipSession.parse_sip_message(indoor_invite)
    assert parsed_indoor["method"] == "INVITE"
    assert parsed_indoor["dev_type"] == DEV_INDOORPHONE
    assert parsed_indoor["headers"].get("targetType") == "HOUSETOHOUSE"


def test_sip_build_housetohouse_invite():
    """Verify building outbound HOUSETOHOUSE INVITE."""
    invite_bytes = AveSipSession.build_invite(
        from_uri="sip:1-1-101@192.168.1.55",
        to_uri="sip:1-1-103@192.168.1.87:5060",
        call_id="intercom-call-999",
        local_rtp_port=AUDIO_PORT,
    )

    invite_str = invite_bytes.decode("utf-8")
    assert "INVITE sip:1-1-103@192.168.1.87:5060 SIP/2.0" in invite_str
    assert "targetType: HOUSETOHOUSE" in invite_str
    assert "callType: CALL_OUT" in invite_str
    assert "iotCallVersion: 1.0.1" in invite_str
    assert "m=audio 8302 RTP/AVP 8" in invite_str  # PCMA payload type 8


def test_sip_build_info_unlock():
    """Verify building SIP INFO COM_REMOTE_UNLOCK_ASK."""
    info_bytes = AveSipSession.build_info_unlock(
        from_uri="sip:1001@192.168.1.55",
        to_uri="sip:doorstation@192.168.1.100",
        call_id="call-12345@192.168.1.100",
        cseq=2,
    )

    info_str = info_bytes.decode("utf-8")
    assert "INFO sip:doorstation@192.168.1.100 SIP/2.0" in info_str
    assert "Content-Type: application/gvs_protocol+json" in info_str
    assert "COM_REMOTE_UNLOCK_ASK" in info_str


@pytest.mark.asyncio
async def test_ave_sip_session_audio_bounded_queue_and_rx():
    """Verify bounded 10-frame audio buffer and RX callback."""
    session = AveSipSession(local_port=5060, rtp_port=AUDIO_PORT)
    session._transport = MagicMock()
    session._remote_rtp_addr = ("192.168.1.100", AUDIO_PORT)

    # Enqueue 15 frames of 320-byte PCM16 (each 20ms)
    frame = b"\x00" * 320
    for i in range(15):
        session.send_pcm16_frame(frame)

    # Queue should be bounded to 10 frames
    assert session.audio_tx_queue_size <= 10

    # Test RX callback with multiple subscribers
    rx_frames_1 = []
    rx_frames_2 = []

    def on_rx_pcm16_1(data: bytes):
        rx_frames_1.append(data)

    def on_rx_pcm16_2(data: bytes):
        rx_frames_2.append(data)

    session.set_rx_pcm16_callback(on_rx_pcm16_1)
    session.add_rx_pcm16_callback(on_rx_pcm16_2)

    # Simulate RTP PCMA packet arrival (12-byte header + 160 bytes PCMA payload)
    rtp_header = b"\x80\x08\x00\x01\x00\x00\x00\xa0\x12\x34\x56\x78"
    alaw_payload = b"\xd5" * 160  # A-law silence
    simulated_rtp = rtp_header + alaw_payload

    session.handle_rtp_packet(simulated_rtp)

    assert len(rx_frames_1) == 1
    assert len(rx_frames_2) == 1
    assert len(rx_frames_1[0]) == 320  # 160 16-bit samples

    # Test removing one callback
    session.remove_rx_pcm16_callback(on_rx_pcm16_2)
    session.handle_rtp_packet(simulated_rtp)
    assert len(rx_frames_1) == 2
    assert len(rx_frames_2) == 1

    # Clean close
    await session.async_close()
    assert session.is_closed is True
