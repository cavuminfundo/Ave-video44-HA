"""SIP signaling and RTP audio bridge session using asyncio.DatagramProtocol."""

import asyncio
import base64
import collections
import hashlib
import json
import logging
import os
import re
import socket
import struct
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import uuid

from ..const import (
    AUDIO_PORT,
    DEV_DOORSTATION,
    DEV_INDOORPHONE,
    DEV_UNKONW,
)
from .protocol import alaw_to_pcm16, pcm16_to_alaw

_LOGGER = logging.getLogger(__name__)


class AveSipSession(asyncio.DatagramProtocol):
    """SIP session and full-duplex RTP audio engine for AVE Video V44."""

    def __init__(
        self,
        local_host: str = "0.0.0.0",
        local_port: int = 5060,
        rtp_port: int = AUDIO_PORT,
    ) -> None:
        self.local_host = local_host
        self.local_port = local_port
        self.rtp_port = rtp_port

        self._transport: Optional[asyncio.DatagramTransport] = None
        self._remote_rtp_addr: Optional[Tuple[str, int]] = None
        self._audio_tx_queue: collections.deque = collections.deque(maxlen=10)
        self._rx_callbacks: Set[Callable[[bytes], None]] = set()

        self._seq = 0
        self._timestamp = 0
        self._ssrc = 0x12345678
        self.is_closed = False

    @property
    def audio_tx_queue_size(self) -> int:
        """Current number of frames buffered in TX queue."""
        return len(self._audio_tx_queue)

    @property
    def _rx_callback(self) -> Optional[Callable[[bytes], None]]:
        """Return primary RX callback for backwards compatibility."""
        return next(iter(self._rx_callbacks), None)

    def add_rx_pcm16_callback(self, callback: Callable[[bytes], None]) -> None:
        """Register an incoming decoded PCM16 audio frame callback."""
        self._rx_callbacks.add(callback)

    def remove_rx_pcm16_callback(self, callback: Callable[[bytes], None]) -> None:
        """Unregister an incoming decoded PCM16 audio frame callback."""
        self._rx_callbacks.discard(callback)

    def set_rx_pcm16_callback(self, callback: Callable[[bytes], None]) -> None:
        """Set callback invoked on incoming decoded PCM16 audio frames."""
        self._rx_callbacks.clear()
        self._rx_callbacks.add(callback)

    def set_remote_rtp_target(self, host: str, port: int) -> None:
        """Set destination IP address and port for RTP audio packets."""
        self._remote_rtp_addr = (host, port)

    def send_pcm16_frame(self, frame: bytes) -> None:
        """Enqueue PCM16 frame for transmission with bounded 10-frame buffer."""
        if self.is_closed:
            return

        self._audio_tx_queue.append(frame)

        if self._transport and self._remote_rtp_addr:
            alaw = pcm16_to_alaw(frame)
            rtp_header = struct.pack(
                "!BBHII",
                0x80,
                8,
                self._seq & 0xFFFF,
                self._timestamp & 0xFFFFFFFF,
                self._ssrc,
            )
            self._seq += 1
            self._timestamp += len(alaw)
            try:
                self._transport.sendto(rtp_header + alaw, self._remote_rtp_addr)
            except Exception as err:
                _LOGGER.error("Failed to send RTP datagram: %s", err)

    def handle_rtp_packet(self, data: bytes) -> None:
        """Process incoming RTP packet, decode PCMA payload to PCM16."""
        if len(data) < 12:
            return

        payload_type = data[1] & 0x7F
        if payload_type != 8:
            return

        alaw_payload = data[12:]
        pcm16 = alaw_to_pcm16(alaw_payload)

        for cb in list(self._rx_callbacks):
            try:
                cb(pcm16)
            except Exception as err:
                _LOGGER.error("Error in audio RX callback: %s", err)

    @classmethod
    def parse_sip_message(cls, raw: bytes) -> Dict[str, Any]:
        """Parse raw SIP datagram into method, headers, dev_type and body."""
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1", errors="replace")

        parts = text.split("\r\n\r\n", 1)
        header_block = parts[0]
        body = parts[1] if len(parts) > 1 else ""

        lines = header_block.split("\r\n")
        first_line = lines[0] if lines else ""
        first_tokens = first_line.split()

        method = first_tokens[0] if first_tokens else ""
        uri = first_tokens[1] if len(first_tokens) > 1 else ""

        headers: Dict[str, str] = {}
        for line in lines[1:]:
            if ":" in line:
                key, val = line.split(":", 1)
                headers[key.strip()] = val.strip()

        call_id = headers.get("Call-ID") or headers.get("i", "")
        cseq = headers.get("CSeq", "")
        from_hdr = headers.get("From") or headers.get("f", "")
        to_hdr = headers.get("To") or headers.get("t", "")

        dev_type = DEV_UNKONW
        if "devType" in headers:
            try:
                dev_type = int(headers["devType"])
            except ValueError:
                pass
        elif "DOORSTATION" in from_hdr:
            dev_type = DEV_DOORSTATION
        elif "IS" in from_hdr:
            dev_type = DEV_INDOORPHONE

        return {
            "method": method,
            "uri": uri,
            "headers": headers,
            "body": body,
            "call_id": call_id,
            "cseq": cseq,
            "from": from_hdr,
            "to": to_hdr,
            "dev_type": dev_type,
        }

    @classmethod
    def build_invite(
        cls,
        from_uri: str,
        to_uri: str,
        call_id: str,
        local_rtp_port: int = AUDIO_PORT,
        cseq: int = 1,
        local_host: str = "0.0.0.0",
        local_port: int = 5060,
    ) -> bytes:
        """Build outbound HOUSETOHOUSE SIP INVITE with SDP offer."""
        sdp = (
            f"v=0\r\n"
            f"o=- 0 0 IN IP4 {local_host}\r\n"
            f"s=AVE Video V44\r\n"
            f"c=IN IP4 {local_host}\r\n"
            f"t=0 0\r\n"
            f"m=audio {local_rtp_port} RTP/AVP 8\r\n"
            f"a=rtpmap:8 PCMA/8000\r\n"
            f"a=sendrecv\r\n"
        )
        lines = [
            f"INVITE {to_uri} SIP/2.0",
            f"Via: SIP/2.0/UDP {local_host}:{local_port};branch=z9hG4bK-{call_id}",
            f"From: <{from_uri}>;tag={call_id}",
            f"To: <{to_uri}>",
            f"Call-ID: {call_id}",
            f"CSeq: {cseq} INVITE",
            f"Contact: <{from_uri}>",
            "targetType: HOUSETOHOUSE",
            "callType: CALL_OUT",
            "iotCallVersion: 1.0.1",
            "Content-Type: application/sdp",
            f"Content-Length: {len(sdp)}",
            "",
            sdp,
        ]
        return "\r\n".join(lines).encode("utf-8")

    @classmethod
    def build_info_unlock(
        cls,
        from_uri: str,
        to_uri: str,
        call_id: str,
        cseq: int = 2,
        local_host: str = "0.0.0.0",
        local_port: int = 5060,
    ) -> bytes:
        """Build SIP INFO with COM_REMOTE_UNLOCK_ASK payload."""
        body = json.dumps({
            "req": "COM_REMOTE_UNLOCK_ASK",
            "reqsn": 1,
            "sip": from_uri,
            "status": 1,
        })
        lines = [
            f"INFO {to_uri} SIP/2.0",
            f"Via: SIP/2.0/UDP {local_host}:{local_port};branch=z9hG4bK-unlock-{cseq}",
            f"From: <{from_uri}>;tag={call_id}",
            f"To: <{to_uri}>",
            f"Call-ID: {call_id}",
            f"CSeq: {cseq} INFO",
            "Content-Type: application/gvs_protocol+json",
            f"Content-Length: {len(body)}",
            "",
            body,
        ]
        return "\r\n".join(lines).encode("utf-8")

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """Datagram transport established."""
        self._transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr: Tuple[str, int]) -> None:
        """Handle incoming datagram: SIP message or RTP packet."""
        if len(data) >= 12 and data[0] == 0x80 and (data[1] & 0x7F) == 8:
            self.handle_rtp_packet(data)
        elif data.startswith((b"INVITE", b"SIP/2.0", b"INFO", b"BYE", b"ACK", b"OPTIONS")):
            msg = self.parse_sip_message(data)
            _LOGGER.debug("Received SIP %s from %s", msg.get("method"), addr)

    def error_received(self, exc: Exception) -> None:
        """Handle transport error."""
        _LOGGER.error("SIP datagram transport error: %s", exc)

    def connection_lost(self, exc: Optional[Exception]) -> None:
        """Mark session closed on connection loss."""
        self.is_closed = True

    async def async_close(self) -> None:
        """Close transport and flush audio queues."""
        self.is_closed = True
        if self._transport:
            self._transport.close()
            self._transport = None
        self._audio_tx_queue.clear()
        self._rx_callbacks.clear()


class CloudSipMediaSession:
    """SIP media session for AVE Cloud (TS-SMART 2-wire) H.264 SRTP video decoding."""

    def __init__(
        self,
        device_id: str,
        sip_username: str,
        sip_password: str,
        target_sip_uri: str,
        user_id: str = "34964",
        target_device_num: str = "1",
        sender_name: str = "Citofono",
        ffmpeg_binary: str = "ffmpeg",
        on_terminated: Optional[Callable[[], None]] = None,
    ) -> None:
        self.device_id = str(device_id)
        self.sip_username = str(sip_username)
        self.sip_password = str(sip_password)
        self.target_sip_uri = str(target_sip_uri)
        self.user_id = str(user_id)
        self.target_device_num = str(target_device_num)
        self.sender_name = str(sender_name)
        self.ffmpeg_binary = ffmpeg_binary
        self.on_terminated = on_terminated

        # Extract user & domain, e.g. "sip:2114136144349364224@eu.open-sips.gvs-icloud.com"
        clean = self.sip_username
        if clean.startswith("sip:"):
            clean = clean[4:]
        if "@" in clean:
            self._sip_user, self._sip_domain = clean.split("@", 1)
        else:
            self._sip_user = clean
            self._sip_domain = "eu.open-sips.gvs-icloud.com"

        self.latest_frame: Optional[bytes] = None
        self.frame_seq: int = 0
        self._first_frame_event = asyncio.Event()
        self._frame_event = asyncio.Event()
        self.is_active: bool = False

        self._mjpeg_buf = bytearray()
        self._sdp_path: Optional[str] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._audio_sock: Optional[socket.socket] = None
        self._video_sock: Optional[socket.socket] = None
        self._rtcp_sock: Optional[socket.socket] = None
        self._ffmpeg_port: Optional[int] = None
        self._ffmpeg_proc: Optional[asyncio.subprocess.Process] = None
        self._tasks: List[asyncio.Task] = []
        self._local_ip: str = "127.0.0.1"
        self._call_id: Optional[str] = None
        self._from_tag: Optional[str] = None
        self._contact_uri: Optional[str] = None
        self._route_headers: List[str] = []

    @staticmethod
    def _parse_digest_challenge(challenge: str) -> Dict[str, str]:
        """Extract key-value pairs from Digest challenge header."""
        out: Dict[str, str] = {}
        for match in re.finditer(r'([a-zA-Z0-9_-]+)="?([^",\r\n]+)"?', challenge):
            out[match.group(1).lower()] = match.group(2)
        return out

    @staticmethod
    def _compute_digest_auth(
        username: str,
        realm: str,
        password: str,
        method: str,
        uri: str,
        nonce: str,
        qop: Optional[str] = None,
        nc: str = "00000001",
        cnonce: str = "avev44ha",
    ) -> str:
        """Compute Digest response and return full Authorization header value."""
        ha1 = hashlib.md5(f"{username}:{realm}:{password}".encode("utf-8")).hexdigest()
        ha2 = hashlib.md5(f"{method}:{uri}".encode("utf-8")).hexdigest()
        if qop and "auth" in qop.lower():
            resp = hashlib.md5(f"{ha1}:{nonce}:{nc}:{cnonce}:auth:{ha2}".encode("utf-8")).hexdigest()
            return (
                f'Digest username="{username}", realm="{realm}", nonce="{nonce}", '
                f'uri="{uri}", response="{resp}", qop=auth, nc={nc}, cnonce="{cnonce}"'
            )
        resp = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode("utf-8")).hexdigest()
        return (
            f'Digest username="{username}", realm="{realm}", nonce="{nonce}", '
            f'uri="{uri}", response="{resp}"'
        )

    _compute_digest_response = _compute_digest_auth

    @staticmethod
    def parse_200_ok_sdp(sdp_text: str) -> Dict[str, Any]:
        """Parse remote SDP from 200 OK response."""
        res: Dict[str, Any] = {
            "remote_ip": "",
            "remote_audio_port": 0,
            "remote_video_port": 0,
            "crypto_suite": "AES_CM_128_HMAC_SHA1_80",
            "crypto_key": "",
            "video_fmtp": "",
        }
        current_media = ""
        for line in sdp_text.splitlines():
            line = line.strip()
            if line.startswith("c=IN IP4 "):
                ip = line.split("c=IN IP4 ")[1].strip()
                if not res["remote_ip"] or current_media == "video":
                    res["remote_ip"] = ip
            elif line.startswith("m=audio "):
                current_media = "audio"
                parts = line.split()
                if len(parts) > 1 and parts[1].isdigit():
                    res["remote_audio_port"] = int(parts[1])
            elif line.startswith("m=video "):
                current_media = "video"
                parts = line.split()
                if len(parts) > 1 and parts[1].isdigit():
                    res["remote_video_port"] = int(parts[1])
            elif line.startswith("a=crypto:") and current_media == "video":
                parts = line.split()
                if len(parts) >= 3:
                    res["crypto_suite"] = parts[1]
                    for p in parts[2:]:
                        if p.startswith("inline:"):
                            res["crypto_key"] = p.split("inline:")[1].split("|")[0].strip()
            elif line.startswith("a=fmtp:96 ") and current_media == "video":
                res["video_fmtp"] = line.split("a=fmtp:96 ")[1].strip()

        res["callee_video_suite"] = res["crypto_suite"]
        res["callee_video_key"] = res["crypto_key"]
        return res

    def _generate_local_sdp(
        self, ffmpeg_port: int, crypto_suite: str, crypto_key: str, video_fmtp: str
    ) -> str:
        """Generate SDP descriptor file for local FFmpeg SRTP listener."""
        lines = [
            "v=0",
            "o=- 0 0 IN IP4 127.0.0.1",
            "s=CloudSipSession",
            "c=IN IP4 127.0.0.1",
            "t=0 0",
            f"m=video {ffmpeg_port} RTP/SAVP 96",
            "a=rtpmap:96 H264/90000",
            f"a=fmtp:96 {video_fmtp}" if video_fmtp else "a=fmtp:96 packetization-mode=1",
            f"a=crypto:1 {crypto_suite} inline:{crypto_key}",
            "",
        ]
        return "\r\n".join(lines)

    def build_register_packet(self, cseq: int = 1, auth: Optional[str] = None) -> str:
        """Build SIP REGISTER packet."""
        call_id = f"reg-{self.device_id}-{uuid.uuid4().hex[:8]}@avev44"
        lines = [
            f"REGISTER sip:{self._sip_domain} SIP/2.0",
            f"Via: SIP/2.0/TCP {self._local_ip}:5060;branch=z9hG4bK-reg-{cseq}",
            f"To: <sip:{self._sip_user}@{self._sip_domain}>",
            f"From: <sip:{self._sip_user}@{self._sip_domain}>;tag={uuid.uuid4().hex[:8]}",
            f"Call-ID: {call_id}",
            f"CSeq: {cseq} REGISTER",
            f"Contact: <sip:{self._sip_user}@{self._local_ip}:5060;transport=tcp>",
            "Expires: 3600",
            "Max-Forwards: 70",
            "User-Agent: AVE-Video44-HA",
        ]
        if auth:
            lines.append(f"Authorization: {auth}")
        lines.extend(["Content-Length: 0", "", ""])
        return "\r\n".join(lines)

    def build_invite_packet(
        self,
        cseq: int,
        local_ip: str,
        audio_port: int,
        video_port: int,
        srtp_audio_key: str,
        srtp_video_key: str,
        auth_header: Optional[str] = None,
        call_id: Optional[str] = None,
    ) -> str:
        """Build outbound SIP INVITE with 14 custom headers and SRTP SDP."""
        cid = call_id or self._call_id or f"inv-{self.device_id}-{uuid.uuid4().hex[:8]}@avev44"
        self._call_id = cid
        sdp = (
            "v=0\r\n"
            f"o={self.user_id} 1000 1000 IN IP4 {local_ip}\r\n"
            "s=AVE Video V44 Cloud\r\n"
            f"c=IN IP4 {local_ip}\r\n"
            "t=0 0\r\n"
            f"m=audio {audio_port} RTP/SAVP 8\r\n"
            "a=rtpmap:8 PCMA/8000\r\n"
            f"a=crypto:1 AES_CM_128_HMAC_SHA1_80 inline:{srtp_audio_key}\r\n"
            "a=sendrecv\r\n"
            f"m=video {video_port} RTP/SAVP 96\r\n"
            "a=rtpmap:96 H264/90000\r\n"
            f"a=crypto:1 AES_CM_128_HMAC_SHA1_80 inline:{srtp_video_key}\r\n"
            "a=sendrecv\r\n"
        )
        sdp_bytes = sdp.encode("utf-8")
        from_tag = self._from_tag or uuid.uuid4().hex[:8]
        self._from_tag = from_tag
        lines = [
            f"INVITE {self.target_sip_uri} SIP/2.0",
            f"Via: SIP/2.0/TCP {local_ip}:5060;branch=z9hG4bK-inv-{cseq}",
            f"To: <{self.target_sip_uri}>",
            f"From: <sip:{self._sip_user}@{self._sip_domain}>;tag={from_tag}",
            f"Call-ID: {cid}",
            f"CSeq: {cseq} INVITE",
            f"Contact: <sip:{self._sip_user}@{local_ip}:5060;transport=tcp>",
            f"targetDeviceNum: {self.target_device_num}",
            "type: 0",
            "callType: 0",
            "iotCallVersion: 1.0.1",
            f"senderId: {self.user_id}",
            "senderType: 3",
            f"senderName: {self.sender_name}",
            f"targetId: {self.device_id}",
            f"callId: {cid}",
            "targetType: 1",
            "enableVideo: 1",
            "enableAudio: 1",
            f"proxyDeviceId: {self.device_id}",
            "proxyFlag: 1",
            "Content-Type: application/sdp",
        ]
        if auth_header:
            lines.append(f"Proxy-Authorization: {auth_header}")
        lines.extend([
            f"Content-Length: {len(sdp_bytes)}",
            "",
            sdp,
        ])
        return "\r\n".join(lines)

    def _feed_mjpeg_bytes(self, chunk: bytes) -> None:
        """Accumulate bytes and parse JPEG frames (0xFFD8 to 0xFFD9)."""
        self._mjpeg_buf.extend(chunk)
        while True:
            start = self._mjpeg_buf.find(b"\xff\xd8")
            if start == -1:
                if len(self._mjpeg_buf) > 4096:
                    del self._mjpeg_buf[:-2]
                break
            end = self._mjpeg_buf.find(b"\xff\xd9", start + 2)
            if end == -1:
                if start > 0:
                    del self._mjpeg_buf[:start]
                break
            frame = bytes(self._mjpeg_buf[start : end + 2])
            del self._mjpeg_buf[: end + 2]
            self.latest_frame = frame
            self.frame_seq += 1
            self._first_frame_event.set()
            self._frame_event.set()

    async def wait_for_first_frame(self, timeout: float = 6.0) -> Optional[bytes]:
        """Wait until the first JPEG frame is decoded."""
        if self.latest_frame is not None:
            return self.latest_frame
        try:
            await asyncio.wait_for(self._first_frame_event.wait(), timeout=timeout)
            return self.latest_frame
        except (asyncio.TimeoutError, asyncio.CancelledError):
            return self.latest_frame

    async def wait_for_next_frame(
        self, last_seq: int, timeout: float = 0.5
    ) -> Tuple[int, Optional[bytes]]:
        """Wait for the next newer decoded frame."""
        if self.frame_seq > last_seq:
            return self.frame_seq, self.latest_frame
        self._frame_event.clear()
        try:
            await asyncio.wait_for(self._frame_event.wait(), timeout=timeout)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass
        return self.frame_seq, self.latest_frame

    async def _read_sip_msg(self) -> Tuple[str, Dict[str, str], str]:
        """Read a complete SIP message over TCP stream."""
        if not self._reader:
            raise ConnectionResetError("Reader not connected")
        data = bytearray()
        while True:
            chunk = await self._reader.read(1024)
            if not chunk:
                raise ConnectionResetError("SIP connection closed by remote server")
            data.extend(chunk)
            idx = data.find(b"\r\n\r\n")
            if idx != -1:
                break
        header_bytes = bytes(data[:idx])
        body_remainder = bytes(data[idx + 4:])
        header_text = header_bytes.decode("utf-8", errors="replace")
        lines = header_text.split("\r\n")
        start_line = lines[0]
        headers: Dict[str, str] = {}
        for line in lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()
        content_len = int(headers.get("content-length", 0))
        needed = content_len - len(body_remainder)
        body_bytes = bytearray(body_remainder)
        while needed > 0:
            chunk = await self._reader.read(min(needed, 4096))
            if not chunk:
                break
            body_bytes.extend(chunk)
            needed -= len(chunk)
        body_text = bytes(body_bytes).decode("utf-8", errors="replace")
        return start_line, headers, body_text

    async def _ffmpeg_stdout_loop(self) -> None:
        """Stream image2pipe stdout from FFmpeg into frame extractor."""
        if not self._ffmpeg_proc or not self._ffmpeg_proc.stdout:
            return
        try:
            while self.is_active:
                chunk = await self._ffmpeg_proc.stdout.read(8192)
                if not chunk:
                    break
                self._feed_mjpeg_bytes(chunk)
        except (asyncio.CancelledError, Exception):
            pass

    async def _udp_relay_loop(
        self, remote_ip: str, remote_video_port: int, remote_audio_port: int
    ) -> None:
        """NAT-punching keepalive and inbound SRTP to FFmpeg loop."""
        dummy_rtp = b"\x80\x60\x00\x01\x00\x00\x00\x00\x12\x34\x56\x78"
        last_punch = 0.0
        while self.is_active:
            now = time.monotonic()
            if now - last_punch >= 0.4:
                last_punch = now
                try:
                    if self._video_sock and remote_video_port:
                        self._video_sock.sendto(dummy_rtp, (remote_ip, remote_video_port))
                    if self._rtcp_sock and remote_video_port:
                        self._rtcp_sock.sendto(dummy_rtp, (remote_ip, remote_video_port + 1))
                    if self._audio_sock and remote_audio_port:
                        self._audio_sock.sendto(dummy_rtp, (remote_ip, remote_audio_port))
                except Exception:
                    pass

            try:
                while self._video_sock:
                    pkt, _ = self._video_sock.recvfrom(65535)
                    if pkt and self._ffmpeg_port:
                        self._video_sock.sendto(pkt, ("127.0.0.1", self._ffmpeg_port))
            except (BlockingIOError, InterruptedError):
                pass
            except Exception:
                pass
            await asyncio.sleep(0.005)

    async def _sip_watch_loop(self) -> None:
        """Watch SIP TCP socket for remote BYE or termination."""
        start_time = time.monotonic()
        try:
            while self.is_active and self._reader:
                if time.monotonic() - start_time > 90.0:
                    break
                try:
                    line = await asyncio.wait_for(self._reader.readline(), timeout=2.0)
                    if not line:
                        break
                    if line.startswith(b"BYE "):
                        _LOGGER.debug("Received remote BYE, terminating session")
                        break
                except asyncio.TimeoutError:
                    continue
        except (asyncio.CancelledError, Exception):
            pass
        finally:
            if self.is_active:
                asyncio.create_task(self.async_stop())

    async def async_start(self) -> bool:
        """Start SIP session over TCP, send REGISTER, INVITE, spin FFmpeg and UDP relay."""
        try:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect((self._sip_domain, 5060))
                self._local_ip = s.getsockname()[0]
                s.close()
            except Exception:
                self._local_ip = "127.0.0.1"

            self._audio_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._audio_sock.setblocking(False)
            self._audio_sock.bind(("0.0.0.0", 0))
            audio_port = self._audio_sock.getsockname()[1]

            self._video_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._video_sock.setblocking(False)
            try:
                self._video_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)
            except Exception:
                pass
            self._video_sock.bind(("0.0.0.0", 0))
            video_port = self._video_sock.getsockname()[1]

            self._rtcp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._rtcp_sock.setblocking(False)
            self._rtcp_sock.bind(("0.0.0.0", 0))

            s_ff = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s_ff.bind(("127.0.0.1", 0))
            self._ffmpeg_port = s_ff.getsockname()[1]
            s_ff.close()

            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self._sip_domain, 5060), timeout=8.0
            )

            # REGISTER
            reg_pkt = self.build_register_packet(cseq=1)
            self._writer.write(reg_pkt.encode("utf-8"))
            await self._writer.drain()

            start_line, headers, body = await asyncio.wait_for(self._read_sip_msg(), timeout=6.0)
            status_code = int(start_line.split()[1]) if len(start_line.split()) > 1 else 0

            if status_code in (401, 407):
                auth_hdr_name = "proxy-authenticate" if status_code == 407 else "www-authenticate"
                challenge = headers.get(auth_hdr_name, "")
                ch_dict = self._parse_digest_challenge(challenge)
                auth_val = self._compute_digest_auth(
                    username=self._sip_user,
                    realm=ch_dict.get("realm", self._sip_domain),
                    password=self.sip_password,
                    method="REGISTER",
                    uri=f"sip:{self._sip_domain}",
                    nonce=ch_dict.get("nonce", ""),
                    qop=ch_dict.get("qop"),
                )
                reg_auth_pkt = self.build_register_packet(cseq=2, auth=auth_val)
                self._writer.write(reg_auth_pkt.encode("utf-8"))
                await self._writer.drain()

                start_line, headers, body = await asyncio.wait_for(self._read_sip_msg(), timeout=6.0)
                status_code = int(start_line.split()[1]) if len(start_line.split()) > 1 else 0

            if status_code != 200:
                _LOGGER.warning("SIP REGISTER failed with status %s", start_line)
                await self.async_stop()
                return False

            # INVITE
            srtp_audio_key = base64.b64encode(os.urandom(30)).decode("ascii")
            srtp_video_key = base64.b64encode(os.urandom(30)).decode("ascii")
            cseq_inv = 1
            inv_pkt = self.build_invite_packet(
                cseq=cseq_inv,
                local_ip=self._local_ip,
                audio_port=audio_port,
                video_port=video_port,
                srtp_audio_key=srtp_audio_key,
                srtp_video_key=srtp_video_key,
            )
            self._writer.write(inv_pkt.encode("utf-8"))
            await self._writer.drain()

            start_line, headers, body = await asyncio.wait_for(self._read_sip_msg(), timeout=8.0)
            status_code = int(start_line.split()[1]) if len(start_line.split()) > 1 else 0

            if status_code in (401, 407):
                ack_pkt = (
                    f"ACK {self.target_sip_uri} SIP/2.0\r\n"
                    f"Via: SIP/2.0/TCP {self._local_ip}:5060;branch=z9hG4bK-inv-{cseq_inv}\r\n"
                    f"To: <{self.target_sip_uri}>\r\n"
                    f"From: <sip:{self._sip_user}@{self._sip_domain}>;tag={self._from_tag}\r\n"
                    f"Call-ID: {self._call_id}\r\n"
                    f"CSeq: {cseq_inv} ACK\r\n"
                    "Content-Length: 0\r\n\r\n"
                )
                self._writer.write(ack_pkt.encode("utf-8"))
                await self._writer.drain()

                auth_hdr_name = "proxy-authenticate" if status_code == 407 else "www-authenticate"
                challenge = headers.get(auth_hdr_name, "")
                ch_dict = self._parse_digest_challenge(challenge)
                auth_val = self._compute_digest_auth(
                    username=self._sip_user,
                    realm=ch_dict.get("realm", self._sip_domain),
                    password=self.sip_password,
                    method="INVITE",
                    uri=self.target_sip_uri,
                    nonce=ch_dict.get("nonce", ""),
                    qop=ch_dict.get("qop"),
                )
                cseq_inv = 2
                inv_auth_pkt = self.build_invite_packet(
                    cseq=cseq_inv,
                    local_ip=self._local_ip,
                    audio_port=audio_port,
                    video_port=video_port,
                    srtp_audio_key=srtp_audio_key,
                    srtp_video_key=srtp_video_key,
                    auth_header=auth_val,
                )
                self._writer.write(inv_auth_pkt.encode("utf-8"))
                await self._writer.drain()
                start_line, headers, body = await asyncio.wait_for(self._read_sip_msg(), timeout=8.0)
                status_code = int(start_line.split()[1]) if len(start_line.split()) > 1 else 0

            deadline = time.monotonic() + 12.0
            while status_code != 200 and time.monotonic() < deadline:
                if status_code >= 400:
                    _LOGGER.warning("SIP INVITE rejected: %s", start_line)
                    await self.async_stop()
                    return False
                rem_timeout = max(0.5, deadline - time.monotonic())
                start_line, headers, body = await asyncio.wait_for(
                    self._read_sip_msg(), timeout=rem_timeout
                )
                status_code = int(start_line.split()[1]) if len(start_line.split()) > 1 else 0

            if status_code != 200:
                _LOGGER.warning("SIP INVITE did not receive 200 OK: %s", start_line)
                await self.async_stop()
                return False

            to_header = headers.get("to", f"<{self.target_sip_uri}>")
            contact_header = headers.get("contact", "")
            contact_match = re.search(r"<([^>]+)>", contact_header)
            self._contact_uri = contact_match.group(1) if contact_match else self.target_sip_uri

            record_routes = headers.get("record-route", "")
            route_lines = []
            if record_routes:
                entries = [r.strip() for r in record_routes.split(",") if r.strip()]
                entries.reverse()
                for e in entries:
                    route_lines.append(f"Route: {e}")
            self._route_headers = route_lines

            ack_200 = [
                f"ACK {self._contact_uri} SIP/2.0",
                f"Via: SIP/2.0/TCP {self._local_ip}:5060;branch=z9hG4bK-ack-{cseq_inv}",
                f"To: {to_header}",
                f"From: <sip:{self._sip_user}@{self._sip_domain}>;tag={self._from_tag}",
                f"Call-ID: {self._call_id}",
                f"CSeq: {cseq_inv} ACK",
            ]
            ack_200.extend(self._route_headers)
            ack_200.extend(["Content-Length: 0", "", ""])
            self._writer.write("\r\n".join(ack_200).encode("utf-8"))
            await self._writer.drain()

            parsed_sdp = self.parse_200_ok_sdp(body)
            remote_ip = parsed_sdp["remote_ip"] or self._sip_domain
            remote_video_port = parsed_sdp["remote_video_port"]
            remote_audio_port = parsed_sdp["remote_audio_port"]

            self._sdp_path = f"/tmp/ave_video44_{self.device_id}.sdp"
            sdp_content = self._generate_local_sdp(
                ffmpeg_port=self._ffmpeg_port,
                crypto_suite=parsed_sdp["crypto_suite"],
                crypto_key=parsed_sdp["crypto_key"],
                video_fmtp=parsed_sdp["video_fmtp"],
            )
            with open(self._sdp_path, "w", encoding="utf-8") as f:
                f.write(sdp_content)
            try:
                os.chmod(self._sdp_path, 0o600)
            except Exception:
                pass

            self._ffmpeg_proc = await asyncio.create_subprocess_exec(
                self.ffmpeg_binary,
                "-loglevel", "error",
                "-fflags", "nobuffer",
                "-flags", "low_delay",
                "-protocol_whitelist", "file,udp,rtp,srtp,crypto",
                "-i", self._sdp_path,
                "-f", "image2pipe",
                "-vcodec", "mjpeg",
                "-q:v", "5",
                "-",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )

            await asyncio.sleep(0.15)
            self.is_active = True

            self._tasks.append(asyncio.create_task(self._ffmpeg_stdout_loop()))
            self._tasks.append(
                asyncio.create_task(
                    self._udp_relay_loop(remote_ip, remote_video_port, remote_audio_port)
                )
            )
            self._tasks.append(asyncio.create_task(self._sip_watch_loop()))

            await self.wait_for_first_frame(timeout=2.5)
            return True
        except Exception as err:
            _LOGGER.error("Failed to start CloudSipMediaSession: %s", err, exc_info=True)
            await self.async_stop()
            return False

    async def async_stop(self) -> None:
        """Terminate SIP session, stop FFmpeg and relay tasks, remove temp SDP."""
        if not self.is_active and not self._writer and not self._ffmpeg_proc:
            return
        self.is_active = False

        if self._writer and self._contact_uri and self._call_id:
            try:
                bye_lines = [
                    f"BYE {self._contact_uri} SIP/2.0",
                    f"Via: SIP/2.0/TCP {self._local_ip}:5060;branch=z9hG4bK-bye-{uuid.uuid4().hex[:6]}",
                    f"To: <{self.target_sip_uri}>",
                    f"From: <sip:{self._sip_user}@{self._sip_domain}>;tag={self._from_tag}",
                    f"Call-ID: {self._call_id}",
                    "CSeq: 10 BYE",
                ]
                bye_lines.extend(self._route_headers)
                bye_lines.extend(["Content-Length: 0", "", ""])
                self._writer.write("\r\n".join(bye_lines).encode("utf-8"))
                await self._writer.drain()
            except Exception:
                pass

        for t in self._tasks:
            t.cancel()
        self._tasks.clear()

        if self._ffmpeg_proc:
            try:
                self._ffmpeg_proc.terminate()
                await asyncio.wait_for(self._ffmpeg_proc.wait(), timeout=1.5)
            except Exception:
                try:
                    self._ffmpeg_proc.kill()
                except Exception:
                    pass
            self._ffmpeg_proc = None

        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
        self._reader = None

        for s in (self._video_sock, self._rtcp_sock, self._audio_sock):
            if s:
                try:
                    s.close()
                except Exception:
                    pass
        self._video_sock = None
        self._rtcp_sock = None
        self._audio_sock = None

        if self._sdp_path and os.path.exists(self._sdp_path):
            try:
                os.remove(self._sdp_path)
            except Exception:
                pass
            self._sdp_path = None

        if self.on_terminated:
            try:
                self.on_terminated()
            except Exception:
                pass
