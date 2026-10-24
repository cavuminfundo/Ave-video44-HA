"""SIP signaling and RTP audio bridge session using asyncio.DatagramProtocol."""

import asyncio
import collections
import json
import logging
import struct
from typing import Any, Callable, Dict, Optional, Set, Tuple

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
