"""Tests for Cloud SIP Media Session SRTP/RTP decoding, packetization, and SDP negotiation."""

import os
import struct
from unittest.mock import MagicMock

from custom_components.ave_video44.core.protocol import alaw_to_pcm16, ulaw_to_pcm16
from custom_components.ave_video44.core.sip_session import (
    CloudSipMediaSession,
    _decrypt_srtp_packet,
    _encrypt_srtp_packet,
    _rtp_header_length,
)


def _build_test_rtp_packet(
    seq: int = 1,
    ssrc: int = 0x12345678,
    pt: int = 8,
    csrc_count: int = 0,
    has_extension: bool = False,
    payload: bytes = b"\x55" * 160,
    padding_bytes: int = 0,
) -> bytes:
    """Helper to construct RFC 3550 RTP packets with optional CSRC, ext, and padding."""
    b0 = 0x80 | (0x20 if padding_bytes > 0 else 0x00) | (0x10 if has_extension else 0x00) | (csrc_count & 0x0F)
    b1 = pt & 0x7F
    ts = 160 * seq
    hdr = struct.pack("!BBHII", b0, b1, seq & 0xFFFF, ts & 0xFFFFFFFF, ssrc & 0xFFFFFFFF)
    for i in range(csrc_count):
        hdr += struct.pack("!I", 0xC0000000 + i)
    if has_extension:
        hdr += struct.pack("!HH", 0xBEDE, 1)  # Profile + 1 word (4 bytes)
        hdr += b"\x11\x22\x33\x44"
    pkt = hdr + payload
    if padding_bytes > 0:
        pkt += b"\x00" * (padding_bytes - 1) + bytes([padding_bytes])
    return pkt


def test_rtp_header_length_bounds():
    """Verify _rtp_header_length validates version, length, and extension bounds."""
    # Too short (<12 bytes)
    assert _rtp_header_length(b"\x80\x00") == -1
    # Invalid RTP version (not 2)
    assert _rtp_header_length(b"\x40\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00") == -1

    # Standard 12-byte header
    std_pkt = _build_test_rtp_packet()
    assert _rtp_header_length(std_pkt) == 12

    # CSRC count = 2 (12 + 8 = 20)
    csrc_pkt = _build_test_rtp_packet(csrc_count=2)
    assert _rtp_header_length(csrc_pkt) == 20
    # Truncated CSRC
    assert _rtp_header_length(csrc_pkt[:16]) == -1

    # Extension present: 12 + 4 (header) + 4 (ext payload) = 20
    ext_pkt = _build_test_rtp_packet(has_extension=True)
    assert _rtp_header_length(ext_pkt) == 20
    # Truncated extension header
    assert _rtp_header_length(ext_pkt[:14]) == -1
    # Truncated extension payload
    assert _rtp_header_length(ext_pkt[:18]) == -1


def test_srtp_decrypt_roundtrip_and_tamper():
    """Verify _decrypt_srtp_packet round-trips with _encrypt_srtp_packet and rejects tampered data."""
    raw_key = os.urandom(30)
    rtp_pkt = _build_test_rtp_packet(seq=42, ssrc=0x9ABCDEF0, pt=8, payload=b"\x2a" * 160)

    # 1. 10-byte auth tag (AES_CM_128_HMAC_SHA1_80)
    srtp_80 = _encrypt_srtp_packet(rtp_pkt, raw_key, seq=42, ssrc=0x9ABCDEF0, roc=0, tag_len=10)
    assert len(srtp_80) == len(rtp_pkt) + 10
    decrypted_80 = _decrypt_srtp_packet(srtp_80, raw_key, roc=0, tag_len=10)
    assert decrypted_80 == rtp_pkt

    # 2. 4-byte auth tag (AES_CM_128_HMAC_SHA1_32)
    srtp_32 = _encrypt_srtp_packet(rtp_pkt, raw_key, seq=42, ssrc=0x9ABCDEF0, roc=1, tag_len=4)
    assert len(srtp_32) == len(rtp_pkt) + 4
    decrypted_32 = _decrypt_srtp_packet(srtp_32, raw_key, roc=1, tag_len=4)
    assert decrypted_32 == rtp_pkt

    # 3. With CSRC and extension
    csrc_ext_pkt = _build_test_rtp_packet(csrc_count=1, has_extension=True, payload=b"\x77" * 160)
    srtp_ext = _encrypt_srtp_packet(csrc_ext_pkt, raw_key, roc=0, tag_len=10)
    assert _decrypt_srtp_packet(srtp_ext, raw_key, roc=0, tag_len=10) == csrc_ext_pkt

    # 4. Tampered auth tag
    tampered_tag = srtp_80[:-1] + bytes([srtp_80[-1] ^ 0xFF])
    assert _decrypt_srtp_packet(tampered_tag, raw_key, roc=0, tag_len=10) is None

    # 5. Tampered ciphertext payload
    tampered_body = srtp_80[:15] + bytes([srtp_80[15] ^ 0xFF]) + srtp_80[16:]
    assert _decrypt_srtp_packet(tampered_body, raw_key, roc=0, tag_len=10) is None

    # 6. Truncated packet
    assert _decrypt_srtp_packet(srtp_80[:18], raw_key, roc=0, tag_len=10) is None

    # 7. Invalid key length
    assert _decrypt_srtp_packet(srtp_80, b"short_key", roc=0, tag_len=10) is None


def test_inbound_audio_socket_srtp_and_symmetric_rtp():
    """Verify _process_inbound_audio_socket decrypts SRTP, updates Symmetric RTP, and dispatches PCM16."""
    session = CloudSipMediaSession(
        device_id="101",
        sip_username="sip:test@example.com",
        sip_password="pass",
        target_sip_uri="sip:target@example.com",
    )
    session.is_active = True
    session._audio_proto = "RTP/SAVP"
    raw_key = os.urandom(30)
    session._srtp_rx_audio_key = raw_key
    session._srtp_rx_tag_len = 10

    received_frames = []
    session.add_rx_pcm16_callback(lambda frame: received_frames.append(frame))

    # G.711 A-law is 160 bytes
    alaw_payload = bytes([i & 0xFF for i in range(160)])
    rtp_pkt = _build_test_rtp_packet(seq=10, ssrc=0x5555, pt=8, payload=alaw_payload)
    srtp_pkt = _encrypt_srtp_packet(rtp_pkt, raw_key, seq=10, ssrc=0x5555, roc=0, tag_len=10)

    # 1. Unauthenticated/spoofed packet from attacker IP
    spoofed_pkt = srtp_pkt[:-2] + b"\x00\x00"
    session._audio_sock = MagicMock()
    session._audio_sock.recvfrom.side_effect = [
        (spoofed_pkt, ("1.2.3.4", 9999)),
        BlockingIOError(),
    ]
    session._process_inbound_audio_socket()

    assert len(received_frames) == 0
    assert session._remote_ip != "1.2.3.4"
    assert session._remote_audio_port != 9999

    # 2. Valid SRTP packet from genuine remote doorstation
    session._audio_sock.recvfrom.side_effect = [
        (srtp_pkt, ("192.168.1.150", 12345)),
        BlockingIOError(),
    ]
    session._process_inbound_audio_socket()

    assert len(received_frames) == 1
    assert len(received_frames[0]) == 320
    assert received_frames[0] == alaw_to_pcm16(alaw_payload)
    assert session._remote_ip == "192.168.1.150"
    assert session._remote_audio_port == 12345
    assert session._rx_last_seq == 10
    assert session._rx_audio_roc == 0


def test_inbound_audio_socket_padding_and_pcmu():
    """Verify _process_inbound_audio_socket strips RTP padding and decodes PCMU (PT=0)."""
    session = CloudSipMediaSession(
        device_id="101",
        sip_username="sip:test@example.com",
        sip_password="pass",
        target_sip_uri="sip:target@example.com",
    )
    session.is_active = True
    session._audio_proto = "RTP/SAVP"
    raw_key = os.urandom(30)
    session._srtp_rx_audio_key = raw_key
    session._srtp_rx_tag_len = 10

    received_frames = []
    session.add_rx_pcm16_callback(lambda frame: received_frames.append(frame))

    # PCMU payload with 4 bytes padding
    ulaw_payload = bytes([(i + 5) & 0xFF for i in range(160)])
    rtp_pkt = _build_test_rtp_packet(seq=20, ssrc=0x6666, pt=0, payload=ulaw_payload, padding_bytes=4)
    srtp_pkt = _encrypt_srtp_packet(rtp_pkt, raw_key, seq=20, ssrc=0x6666, roc=0, tag_len=10)

    session._audio_sock = MagicMock()
    session._audio_sock.recvfrom.side_effect = [
        (srtp_pkt, ("192.168.1.150", 12345)),
        BlockingIOError(),
    ]
    session._process_inbound_audio_socket()

    assert len(received_frames) == 1
    assert len(received_frames[0]) == 320
    assert received_frames[0] == ulaw_to_pcm16(ulaw_payload)


def test_inbound_audio_socket_roc_rollover_and_out_of_order():
    """Verify RFC 3711 monotonic ROC rollover across 65535 -> 0 without duplicate increment."""
    session = CloudSipMediaSession(
        device_id="101",
        sip_username="sip:test@example.com",
        sip_password="pass",
        target_sip_uri="sip:target@example.com",
    )
    session.is_active = True
    session._audio_proto = "RTP/SAVP"
    raw_key = os.urandom(30)
    session._srtp_rx_audio_key = raw_key
    session._srtp_rx_tag_len = 10

    # Start at seq 65535, ROC 0
    pkt_65535 = _encrypt_srtp_packet(
        _build_test_rtp_packet(seq=65535, ssrc=0x7777),
        raw_key,
        seq=65535,
        ssrc=0x7777,
        roc=0,
    )
    session._audio_sock = MagicMock()
    session._audio_sock.recvfrom.side_effect = [(pkt_65535, ("192.168.1.150", 12345)), BlockingIOError()]
    session._process_inbound_audio_socket()

    assert session._rx_last_seq == 65535
    assert session._rx_audio_roc == 0

    # Next packet rolls over to seq 0, ROC 1
    pkt_0 = _encrypt_srtp_packet(
        _build_test_rtp_packet(seq=0, ssrc=0x7777),
        raw_key,
        seq=0,
        ssrc=0x7777,
        roc=1,
    )
    session._audio_sock.recvfrom.side_effect = [(pkt_0, ("192.168.1.150", 12345)), BlockingIOError()]
    session._process_inbound_audio_socket()

    assert session._rx_last_seq == 0
    assert session._rx_audio_roc == 1

    # Late arrival: seq 65534 from ROC 0 (out of order)
    pkt_65534 = _encrypt_srtp_packet(
        _build_test_rtp_packet(seq=65534, ssrc=0x7777),
        raw_key,
        seq=65534,
        ssrc=0x7777,
        roc=0,
    )
    session._audio_sock.recvfrom.side_effect = [(pkt_65534, ("192.168.1.150", 12345)), BlockingIOError()]
    session._process_inbound_audio_socket()

    # Monotonic high-water mark remains ROC 1, seq 0
    assert session._rx_last_seq == 0
    assert session._rx_audio_roc == 1


def test_inbound_audio_socket_plain_rtp_avp_and_anti_downgrade():
    """Verify plain RTP/AVP accepted only when proto is RTP/AVP and rejected on RTP/SAVP."""
    session = CloudSipMediaSession(
        device_id="101",
        sip_username="sip:test@example.com",
        sip_password="pass",
        target_sip_uri="sip:target@example.com",
    )
    session.is_active = True
    session._audio_proto = "RTP/SAVP"
    session._srtp_rx_audio_key = os.urandom(30)

    plain_pkt = _build_test_rtp_packet(seq=1, pt=8)
    session._audio_sock = MagicMock()
    session._audio_sock.recvfrom.side_effect = [(plain_pkt, ("192.168.1.150", 12345)), BlockingIOError()]

    # When negotiated proto is RTP/SAVP, plaintext packets MUST be dropped
    session._process_inbound_audio_socket()
    assert session._rx_last_seq is None
    assert session._remote_ip is None

    # When negotiated proto is RTP/AVP, plaintext is accepted
    session._audio_proto = "RTP/AVP"
    session._audio_sock.recvfrom.side_effect = [(plain_pkt, ("192.168.1.150", 12345)), BlockingIOError()]
    session._process_inbound_audio_socket()
    assert session._rx_last_seq == 1
    assert session._remote_ip == "192.168.1.150"


def test_send_pcm16_frame_rtp_savp_vs_rtp_avp():
    """Verify send_pcm16_frame transmits SRTP on RTP/SAVP and plaintext RTP on RTP/AVP."""
    session = CloudSipMediaSession(
        device_id="101",
        sip_username="sip:test@example.com",
        sip_password="pass",
        target_sip_uri="sip:target@example.com",
    )
    session.is_active = True
    session._remote_ip = "192.168.1.150"
    session._remote_audio_port = 12345
    session._audio_payload_type = 8
    session._srtp_tx_audio_key = os.urandom(30)
    session._audio_sock = MagicMock()

    # 1. RTP/SAVP -> SRTP ciphertext + 10B HMAC tag
    session._use_srtp_tx = True
    session._srtp_tx_tag_len = 10
    session.send_pcm16_frame(b"\x00\x00" * 160)

    sent_pkt, target = session._audio_sock.sendto.call_args[0]
    assert target == ("192.168.1.150", 12345)
    assert len(sent_pkt) == 12 + 160 + 10  # 182 bytes

    # 2. RTP/AVP -> Plain RTP
    session._use_srtp_tx = False
    session.send_pcm16_frame(b"\x00\x00" * 160)
    sent_plain, _ = session._audio_sock.sendto.call_args[0]
    assert len(sent_plain) == 12 + 160  # 172 bytes
    assert sent_plain[1] & 0x7F == 8


def test_build_invite_packet_pcma_first_and_sdp_suite_retention():
    """Verify build_invite_packet offers PCMA first and parse_200_ok_sdp does not overwrite crypto suite."""
    session = CloudSipMediaSession(
        device_id="test_pcma_first",
        sip_username="sip:test@example.com",
        sip_password="pass",
        target_sip_uri="sip:target@example.com",
    )
    invite = session.build_invite_packet(
        cseq=1,
        local_ip="192.168.1.50",
        audio_port=10000,
        video_port=10002,
        srtp_audio_key="aXVsaWFuMTIzNDU2Nzg5MDEyMzQ1Njc4OTA=",
        srtp_video_key="dmlkZW8xMjM0NTY3ODkwMTIzNDU2Nzg5MDE=",
    )
    assert "m=audio 10000 RTP/SAVP 8 0 101" in invite
    assert invite.index("a=rtpmap:8 PCMA/8000") < invite.index("a=rtpmap:0 PCMU/8000")

    # Verify parse_200_ok_sdp keeps first suite and does not overwrite with subsequent _32
    multi_crypto_sdp = (
        "v=0\r\n"
        "c=IN IP4 192.168.1.200\r\n"
        "m=audio 20000 RTP/SAVP 8\r\n"
        "a=rtpmap:8 PCMA/8000\r\n"
        "a=crypto:1 AES_CM_128_HMAC_SHA1_80 inline:Zmlyc3Rfc3VpdGVfa2V5MTIzNDU2Nzg5MDEyMzQ1Njc4OTA=\r\n"
        "a=crypto:2 AES_CM_128_HMAC_SHA1_32 inline:c2Vjb25kX3N1aXRlX2tleTEyMzQ1Njc4OTAxMjM0NTY3ODkw=\r\n"
        "m=video 20002 RTP/SAVP 96\r\n"
        "a=rtpmap:96 H264/90000\r\n"
        "a=crypto:1 AES_CM_128_HMAC_SHA1_80 inline:dmlkZW9rZXkxMjM0NTY3ODkwMTIzNDU2Nzg5MDE=\r\n"
    )
    parsed = CloudSipMediaSession.parse_200_ok_sdp(multi_crypto_sdp)
    assert parsed["callee_audio_suite"] == "AES_CM_128_HMAC_SHA1_80"
    assert parsed["callee_audio_key"] == "Zmlyc3Rfc3VpdGVfa2V5MTIzNDU2Nzg5MDEyMzQ1Njc4OTA="
