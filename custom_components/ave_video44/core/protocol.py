"""AVE Video V44 / GVS binary protocol framing, hashing, and audio codecs."""

import base64
import hashlib
import hmac
import struct
from typing import Any, Dict, Optional

from ..const import (
    DEFAULT_APP_SECRET,
    MAGIC_HEADER,
)


def compute_gvs_sign(params: Dict[str, Any], secret: str = DEFAULT_APP_SECRET) -> str:
    """Compute HMAC-SHA1 signature conforming to AVE/GVS cloud."""
    sorted_pairs = [
        f"{k}={params[k]}"
        for k in sorted(params.keys())
        if k != "sign" and params[k] is not None and str(params[k]).strip() != ""
    ]
    query_str = "&".join(sorted_pairs)
    b64_qs = base64.b64encode(query_str.encode("utf-8"))
    mac = hmac.new(secret.encode("utf-8"), b64_qs, hashlib.sha1).digest()
    return base64.b64encode(mac).decode("utf-8").lower()


def hash_password_sha256(password: str) -> str:
    """Return lowercase hex SHA-256 digest of password."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest().lower()


def build_gvs_udp_packet(
    func_code: int,
    cmd_code: int,
    src_dev_type: int,
    src_room: bytes,
    dst_dev_type: int,
    dst_room: bytes,
    data: bytes = b"",
    crc: int = 0,
) -> bytes:
    """Build binary UDP packet conforming to GVS Protocol.

    Magic (10 bytes) + Length (2 bytes) + Payload (16 + len(data) bytes) + CRC (2 bytes).
    """
    padded_src = src_room[:6].ljust(6, b"\x00")
    padded_dst = dst_room[:6].ljust(6, b"\x00")

    payload_length = 16 + len(data)
    header = MAGIC_HEADER + struct.pack(">H", payload_length)
    body = (
        struct.pack("!BB", func_code, cmd_code)
        + struct.pack("!B", src_dev_type)
        + padded_src
        + struct.pack("!B", dst_dev_type)
        + padded_dst
        + data
    )
    trailer = struct.pack(">H", crc)
    return header + body + trailer


def parse_gvs_udp_packet(packet: bytes) -> Dict[str, Any]:
    """Parse incoming GVS binary UDP packet and validate magic header and boundaries."""
    if len(packet) < 12:
        raise ValueError(f"Packet too short: {len(packet)} bytes (expected >= 12)")

    if not packet.startswith(MAGIC_HEADER):
        raise ValueError(f"Invalid magic header: {packet[:10]!r}")

    payload_length = struct.unpack_from(">H", packet, 10)[0]
    expected_min_len = 12 + payload_length
    if len(packet) < expected_min_len:
        raise ValueError(
            f"Truncated packet: length {len(packet)} < expected {expected_min_len}"
        )

    func_code = packet[12]
    cmd_code = packet[13]
    src_dev_type = packet[14]
    src_room = packet[15:21]
    dst_dev_type = packet[21]
    dst_room = packet[22:28]
    data = packet[28 : 12 + payload_length]

    crc = 0
    if len(packet) >= 12 + payload_length + 2:
        crc = struct.unpack_from(">H", packet, 12 + payload_length)[0]

    return {
        "func_code": func_code,
        "cmd_code": cmd_code,
        "is_reply": bool(cmd_code & 0x80),
        "src_dev_type": src_dev_type,
        "src_room": src_room,
        "dst_dev_type": dst_dev_type,
        "dst_room": dst_room,
        "data": data,
        "crc": crc,
    }


# Pure-Python ITU-T G.711 A-law lookup tables for Python 3.13+ compatibility without audioop.

def _alaw2linear(a_val: int) -> int:
    a_val ^= 0x55
    t = (a_val & 0x0F) << 4
    seg = (a_val & 0x70) >> 4
    if seg == 0:
        t += 8
    elif seg == 1:
        t += 0x108
    else:
        t += 0x108
        t <<= seg - 1
    return t if (a_val & 0x80) else -t


_SEG_AEND = (0x1F, 0x3F, 0x7F, 0xFF, 0x1FF, 0x3FF, 0x7FF, 0xFFF)


def _linear2alaw(pcm_val: int) -> int:
    pcm_val >>= 3
    if pcm_val >= 0:
        mask = 0xD5
    else:
        mask = 0x55
        pcm_val = -pcm_val - 1

    seg = 8
    for i, boundary in enumerate(_SEG_AEND):
        if pcm_val <= boundary:
            seg = i
            break

    if seg >= 8:
        return 0x7F ^ mask

    aval = seg << 4
    if seg < 2:
        aval |= (pcm_val >> 1) & 0x0F
    else:
        aval |= (pcm_val >> seg) & 0x0F
    return aval ^ mask


_ALAW_TO_PCM16_BYTES = [struct.pack("<h", _alaw2linear(i)) for i in range(256)]

_PCM16_TO_ALAW_TABLE = bytes(
    _linear2alaw(u if u < 32768 else u - 65536) for u in range(65536)
)


def alaw_to_pcm16(alaw_data: bytes) -> bytes:
    """Convert G.711a (PCMA) bytes to 16-bit little-endian linear PCM."""
    table = _ALAW_TO_PCM16_BYTES
    return b"".join(table[b] for b in alaw_data)


def pcm16_to_alaw(pcm16_data: bytes) -> bytes:
    """Convert 16-bit little-endian linear PCM bytes to G.711a (PCMA) bytes."""
    table = _PCM16_TO_ALAW_TABLE
    num_samples = len(pcm16_data) // 2
    out = bytearray(num_samples)
    for i in range(num_samples):
        idx = pcm16_data[2 * i] | (pcm16_data[2 * i + 1] << 8)
        out[i] = table[idx]
    return bytes(out)
