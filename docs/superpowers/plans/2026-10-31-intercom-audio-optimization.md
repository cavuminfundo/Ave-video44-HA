# Intercom Audio Optimization, Anti-Aliasing & SIP Resilience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate perceived latency, robotic/metallic audio distortion, acoustic resonance, local microphone sidetone echo, and transient SIP connection drops (`ConnectionResetError`) in the AVE Video V44 custom component.

**Architecture:**
- **Frontend (WebAudio API):**
  1. Insert a 3400 Hz Butterworth low-pass `BiquadFilterNode` prior to PCM resampling, preventing Nyquist frequency foldback and metallic voice aliasing when downsampling 48 kHz / 44.1 kHz input to 8 kHz G.711 PCMA.
  2. Reduce `ScriptProcessorNode` buffer size from 2048 to 1024 samples, halving input capture latency from ~43 ms to ~21 ms and generating steady single 20 ms frames (160 samples at 8 kHz) instead of bursty 40 ms packet pairs.
  3. Zero out `outputBuffer` via `outputData.fill(0)` in `onaudioprocess` before forwarding to `audioCtx.destination`, decoupling microphone capture from browser speaker output and permanently eliminating local sidetone loopback and acoustic resonance.
  4. Implement an adaptive RX dynamic jitter buffer with 40 ms target playhead and strict 100 ms packet drift drop threshold, discarding excess packets before buffer node allocation to prevent buffer bloat, comb filtering, and overlapping audio echoes.
  5. In `_cleanupCall()`, clear `this._scriptProcessor.onaudioprocess = null;` and disconnect `this._audioSourceNode` to avoid garbage collection memory leaks.
- **Backend (WebSocket API & SIP Session):**
  1. Add an optional `ack` boolean parameter (default `False`) to the `ave_video44/audio_tx` WebSocket command. Implement true fire-and-forget semantics when `ack=False`: suppress `WebSocketError` and `Exception` raises/send_error responses, log at debug level, and avoid sending result JSON messages back to the client (saving 50 JSON messages per second). Only when `ack=True`, return success results or dispatch `send_error`.
  2. Increase the SIP `REGISTER` retry sleep duration from 0.5s to 3.0s upon socket timeout, maintaining buffer flush (`self._rx_buf.clear()`) and terminal re-raise (`else: raise`), in strict compliance with OpenSIPS and AVE TS-SMART 2-wire bus cooldown constraints (Lesson 26).
- **Versioning & Governance:**
  1. Synchronize SemVer version to `1.3.5` across `custom_components/ave_video44/manifest.json`, `pyproject.toml`, `custom_components/ave_video44/frontend/ave-video44-card.js`, and `custom_components/ave_video44/__init__.py`.
  2. Document changes in `CHANGELOG.md` with complete bilingual release notes (English and Italian).

**Tech Stack:** Python 3.12 / 3.13, Home Assistant Core WebSocket API, WebAudio API (ES6 JavaScript), SIP TCP (RFC 3261), G.711 A-law (PCMA) / SRTP (RFC 3711).

---

## Global Constraints

- **Ponytail Ladder:** Strict anti-overengineering. No unnecessary abstractions, no external libraries when WebAudio and standard asyncio primitives suffice.
- **Antislop Code & UI:** No decorative banners, emojis, or ceremonial comments in codebase. Clean, idiomatic test assertions without ternary slop.
- **Legacy WebView Compatibility:** Absolute ban on optional chaining (`?.`) and nullish coalescing (`??`) in `custom_components/ave_video44/frontend/ave-video44-card.js`.
- **Zero Plaintext Secrets:** No passwords, nonces, or tokens logged in clear text.
- **Zero Placeholders:** No `TODO`, `TBD`, or `implement later` in code or tests.

---

## Domain Skills & Sub-Agent Roster (N-Domain Mapping)

1. **Frontend Domain:**
   - Worker Type: `frontend_audio_worker`
   - Skill: `frontend-mobile-security-xss-scan`
   - Companion: `antislop-ui`
   - Target File: `custom_components/ave_video44/frontend/ave-video44-card.js`
   - Test Target: `tests/test_frontend_and_blueprint.py`

2. **Backend Domain:**
   - Worker Type: `backend_audio_worker`
   - Skill: `python-pro`, `async-python-patterns`
   - Companion: `antislop-code`, `ponytail`
   - Target Files: `custom_components/ave_video44/websocket_api.py`, `custom_components/ave_video44/core/sip_session.py`
   - Test Targets: `tests/test_websocket_api.py`, `tests/test_cloud_sip_video.py`, `tests/test_entities_and_ws.py`

3. **Release & Governance Domain:**
   - Worker Type: `release_worker`
   - Companion: `ponytail`
   - Target Files: `custom_components/ave_video44/manifest.json`, `pyproject.toml`, `custom_components/ave_video44/__init__.py`, `CHANGELOG.md`
   - Test Target: `tests/test_repo_governance.py`

---

## Implementation Tasks

### Task 1: Backend WebSocket Audio TX True Fire-and-Forget & SIP Register Cooldown

**Files:**
- Modify: `custom_components/ave_video44/websocket_api.py:97-170`
- Modify: `custom_components/ave_video44/core/sip_session.py:1550-1566`
- Create: `tests/test_websocket_api.py`
- Modify: `tests/test_cloud_sip_video.py:1635-1695`
- Modify: `tests/test_entities_and_ws.py:770-791`

**Interfaces:**
- Consumes: WebSocket command message dictionary with optional `ack: bool` (default `False`).
- Produces: True fire-and-forget handling (suppression of errors and acknowledgments when `ack=False`); 3.0s sleep backoff on initial SIP `REGISTER` timeout with buffer clear and terminal re-raise intact.

- [ ] **Step 1: Write tests in `tests/test_websocket_api.py` and update `tests/test_cloud_sip_video.py`**

Create `tests/test_websocket_api.py`:
```python
"""Tests for WebSocket API audio transmission and call control commands."""

import base64
from unittest.mock import MagicMock
import pytest

from custom_components.ave_video44.const import DOMAIN
import custom_components.ave_video44.websocket_api as ws_api


@pytest.mark.asyncio
async def test_ws_audio_tx_fire_and_forget_default_no_ack(mock_hass, mock_coordinator):
    """Verify ave_video44/audio_tx defaults to fire-and-forget without sending JSON ack."""
    mock_hass.data[DOMAIN] = {"entries": {mock_coordinator.entry_id: mock_coordinator}}
    conn = MagicMock()
    conn.send_result = MagicMock()
    conn.send_error = MagicMock()

    pcm16_data = b"\x00\x02" * 160
    b64_payload = base64.b64encode(pcm16_data).decode("ascii")

    msg = {
        "id": 101,
        "type": "ave_video44/audio_tx",
        "entry_id": mock_coordinator.entry_id,
        "device_id": 9991,
        "payload": b64_payload,
    }

    await ws_api.ws_audio_tx(mock_hass, conn, msg)

    # Audio frame must be forwarded to SIP session
    mock_coordinator.sip_session.send_pcm16_frame.assert_called_once_with(pcm16_data)
    # Default fire-and-forget must NOT send result or error message
    conn.send_result.assert_not_called()
    conn.send_error.assert_not_called()


@pytest.mark.asyncio
async def test_ws_audio_tx_fire_and_forget_suppresses_missing_session(mock_hass, mock_coordinator):
    """Verify missing SIP session is silently dropped in fire-and-forget mode without raising."""
    mock_hass.data[DOMAIN] = {"entries": {mock_coordinator.entry_id: mock_coordinator}}
    mock_coordinator.sip_session = None
    if hasattr(mock_coordinator, "cloud_sip_sessions"):
        mock_coordinator.cloud_sip_sessions.clear()

    conn = MagicMock()
    conn.send_result = MagicMock()
    conn.send_error = MagicMock()

    msg = {
        "id": 102,
        "type": "ave_video44/audio_tx",
        "entry_id": mock_coordinator.entry_id,
        "device_id": 9991,
        "payload": "AAAA",
        "ack": False,
    }

    # Must complete cleanly without raising WebSocketError
    await ws_api.ws_audio_tx(mock_hass, conn, msg)
    conn.send_result.assert_not_called()
    conn.send_error.assert_not_called()


@pytest.mark.asyncio
async def test_ws_audio_tx_explicit_ack_true(mock_hass, mock_coordinator):
    """Verify ave_video44/audio_tx sends JSON success result when ack is explicitly true."""
    mock_hass.data[DOMAIN] = {"entries": {mock_coordinator.entry_id: mock_coordinator}}
    conn = MagicMock()
    conn.send_result = MagicMock()
    conn.send_error = MagicMock()

    pcm16_data = b"\x01\x03" * 160
    b64_payload = base64.b64encode(pcm16_data).decode("ascii")

    msg = {
        "id": 103,
        "type": "ave_video44/audio_tx",
        "entry_id": mock_coordinator.entry_id,
        "device_id": 9991,
        "payload": b64_payload,
        "ack": True,
    }

    await ws_api.ws_audio_tx(mock_hass, conn, msg)

    mock_coordinator.sip_session.send_pcm16_frame.assert_called_once_with(pcm16_data)
    conn.send_result.assert_called_once_with(103, {"success": True})
    conn.send_error.assert_not_called()


@pytest.mark.asyncio
async def test_ws_audio_tx_error_handling_respects_ack(mock_hass, mock_coordinator):
    """Verify error responses are only sent over WebSocket when ack is true."""
    mock_hass.data[DOMAIN] = {"entries": {mock_coordinator.entry_id: mock_coordinator}}
    conn = MagicMock()
    conn.send_result = MagicMock()
    conn.send_error = MagicMock()

    # Broken base64 to trigger exception in handler
    msg_no_ack = {
        "id": 104,
        "type": "ave_video44/audio_tx",
        "entry_id": mock_coordinator.entry_id,
        "device_id": 9991,
        "payload": "invalid_base64_%%%!",
        "ack": False,
    }

    await ws_api.ws_audio_tx(mock_hass, conn, msg_no_ack)
    conn.send_error.assert_not_called()
    conn.send_result.assert_not_called()

    msg_with_ack = {
        "id": 105,
        "type": "ave_video44/audio_tx",
        "entry_id": mock_coordinator.entry_id,
        "device_id": 9991,
        "payload": "invalid_base64_%%%!",
        "ack": True,
    }

    await ws_api.ws_audio_tx(mock_hass, conn, msg_with_ack)
    conn.send_error.assert_called_once_with(105, "audio_tx_failed", pytest.ANY)
```

Update `tests/test_cloud_sip_video.py`:
Reuse and update existing test `test_cloud_sip_media_session_register_retry_four_attempts` (lines 1636-1695) to assert `3.0` in sleep backoff durations:
```python
@pytest.mark.asyncio
async def test_cloud_sip_media_session_register_retry_four_attempts(monkeypatch):
    """Verify REGISTER retries up to 4 times with 2.5s read timeout and 3.0s backoff."""
    from custom_components.ave_video44.core.sip_session import CloudSipMediaSession

    monkeypatch.setattr(CloudSipMediaSession, "_last_session_stop_ts", 0.0)

    sess = CloudSipMediaSession(
        device_id="9991",
        sip_username="user",
        sip_password="pwd",
        target_sip_uri="sip:101@cloud",
    )

    mock_reader = AsyncMock()
    mock_writer = MagicMock()
    mock_writer.write = MagicMock()
    mock_writer.drain = AsyncMock()
    mock_writer.close = MagicMock()
    mock_writer.wait_closed = AsyncMock()

    attempt_count = 0
    sdp_200 = (
        "v=0\r\n"
        "c=IN IP4 51.144.180.20\r\n"
        "m=audio 25000 RTP/SAVP 8\r\n"
        "m=video 25002 RTP/SAVP 96\r\n"
        "a=rtpmap:96 H264/90000\r\n"
        "a=crypto:1 AES_CM_128_HMAC_SHA1_80 inline:cmVtb3RldmlkZW9rZXkxMjM0NTY3ODkwMTIzNDU2\r\n"
    )

    async def _mock_read():
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 3:
            raise asyncio.TimeoutError()
        elif attempt_count == 3:
            return "SIP/2.0 200 OK", {"content-length": "0"}, ""
        else:
            return "SIP/2.0 200 OK", {"content-length": str(len(sdp_200)), "contact": "<sip:target@test.com>"}, sdp_200

    sess._read_sip_msg = _mock_read
    sess.wait_for_first_frame = AsyncMock(return_value=b"\xff\xd8frame\xff\xd9")

    with patch("asyncio.open_connection", return_value=(mock_reader, mock_writer)), \
         patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec, \
         patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        fake_proc = MagicMock()
        fake_proc.stdout = AsyncMock()
        fake_proc.stdout.read = AsyncMock(return_value=b"")
        fake_proc.wait = AsyncMock()
        fake_proc.terminate = MagicMock()
        fake_proc.kill = MagicMock()
        mock_exec.return_value = fake_proc

        started = await asyncio.wait_for(sess.async_start(), timeout=2.0)
        assert started is True
        assert attempt_count >= 3

        # Verify 3.0s backoff sleep per Lesson 26
        sleep_durations = [call.args[0] for call in mock_sleep.call_args_list if call.args]
        assert 3.0 in sleep_durations, f"Expected 3.0s backoff in sleep calls, got: {sleep_durations}"

        await sess.async_stop()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
uv run --with pytest --with cryptography --with pytest-asyncio --with pyyaml pytest tests/test_websocket_api.py tests/test_cloud_sip_video.py -k "register_retry_four_attempts or audio_tx" -v
```
Expected: FAIL.

- [ ] **Step 3: Implement changes in `websocket_api.py` and `sip_session.py`**

In `custom_components/ave_video44/websocket_api.py`:
1. Update schema to include optional `ack`:
```python
@websocket_api.websocket_command({
    vol.Required("type"): "ave_video44/audio_tx",
    vol.Optional("entry_id"): str,
    vol.Required("device_id"): vol.Any(int, str),
    vol.Required("payload"): str,
    vol.Optional("ack", default=False): vol.Coerce(bool),
})
@websocket_api.async_response
async def ws_audio_tx(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: Dict[str, Any],
) -> None:
    """Receive PCM16 audio from Lovelace card and send to RTP engine."""
    coordinator = _get_coordinator(hass, msg.get("entry_id"), msg.get("device_id"))
    device_id = msg.get("device_id")
    is_ack = bool(msg.get("ack", False))
    try:
        session = get_active_sip_session(coordinator, device_id)
        if not session:
            if is_ack:
                raise websocket_api.WebSocketError(
                    "not_found", f"No active SIP session for device {device_id}"
                )
            _LOGGER.debug("audio_tx dropped: no active SIP session for device %s", device_id)
            return

        pcm16_data = base64.b64decode(msg["payload"])
        now = time.monotonic()
        session_key = (id(connection), str(device_id))
        stats = _AUDIO_TX_SESSIONS.get(session_key)
        if not stats or (now - stats["last_active"] > 5.0):
            _LOGGER.debug(
                "audio_tx first frame device=%s bytes=%d",
                device_id,
                len(pcm16_data),
            )
            stats = {
                "frames": 1,
                "bytes": len(pcm16_data),
                "last_log": now,
                "last_frames": 0,
                "last_active": now,
            }
            _AUDIO_TX_SESSIONS[session_key] = stats
        else:
            stats["frames"] += 1
            stats["bytes"] += len(pcm16_data)
            stats["last_active"] = now
            if now - stats["last_log"] >= 5.0:
                elapsed = now - stats["last_log"]
                rate = (stats["frames"] - stats["last_frames"]) / elapsed if elapsed > 0 else 0.0
                _LOGGER.debug(
                    "audio_tx device=%s frames=%d bytes=%d rate=%.1f fps",
                    device_id,
                    stats["frames"],
                    stats["bytes"],
                    rate,
                )
                stats["last_log"] = now
                stats["last_frames"] = stats["frames"]

        if len(_AUDIO_TX_SESSIONS) > 32:
            stale = [k for k, v in _AUDIO_TX_SESSIONS.items() if now - v.get("last_active", 0.0) > 30.0]
            for k in stale:
                _AUDIO_TX_SESSIONS.pop(k, None)

        if hasattr(session, "send_pcm16_frame"):
            session.send_pcm16_frame(pcm16_data)
        elif hasattr(session, "send_audio_frame"):
            session.send_audio_frame(pcm16_data)

        if is_ack:
            connection.send_result(msg["id"], {"success": True})
    except websocket_api.WebSocketError:
        if is_ack:
            raise
        _LOGGER.debug("audio_tx WebSocketError suppressed in fire-and-forget mode")
    except Exception as err:
        _LOGGER.error("Failed to forward audio frame: %s", err)
        if is_ack:
            connection.send_error(msg["id"], "audio_tx_failed", str(err))
```

In `custom_components/ave_video44/core/sip_session.py`:
Update lines 1552-1566:
```python
                except asyncio.TimeoutError:
                    if reg_attempt < 3:
                        _LOGGER.warning("Timeout waiting for initial REGISTER response, retrying in 3.0s...")
                        if self._writer:
                            try:
                                self._writer.close()
                                await self._writer.wait_closed()
                            except Exception:
                                pass
                            self._writer = None
                        self._reader = None
                        self._rx_buf.clear()
                        await asyncio.sleep(3.0)
                    else:
                        raise
```

In `tests/test_entities_and_ws.py`:
Update `test_ws_audio_tx` (line 780) to include `"ack": True`:
```python
    msg = {
        "id": 2,
        "type": "ave_video44/audio_tx",
        "entry_id": mock_coordinator.entry_id,
        "device_id": 9991,
        "payload": b64_payload,
        "ack": True,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
uv run --with pytest --with cryptography --with pytest-asyncio --with pyyaml pytest tests/test_websocket_api.py tests/test_cloud_sip_video.py tests/test_entities_and_ws.py -k "register_retry_four_attempts or audio_tx" -v
```
Expected: PASS.

---

### Task 2: Frontend WebAudio Anti-Aliasing, Low-Latency Chunking & Jitter Buffer

**Files:**
- Modify: `custom_components/ave_video44/frontend/ave-video44-card.js:15-30, 1143-1318`
- Modify: `tests/test_frontend_and_blueprint.py:449-465`

**Interfaces:**
- Consumes: Microphone `MediaStream` from browser `getUserMedia`.
- Produces: 3400 Hz low-pass filtered audio, 1024-sample `ScriptProcessorNode`, `outputData.fill(0)` microphone isolation, explicit early packet discard before buffer allocation for packets exceeding 100 ms jitter drift, and complete GC cleanup (`onaudioprocess = null`, disconnect `this._audioSourceNode`).

- [ ] **Step 1: Update and add tests in `tests/test_frontend_and_blueprint.py`**

1. Replace existing test `test_card_audio_rx_jitter_buffer_clamping` (lines 449-462) with new 40ms playhead and 100ms packet discard assertions:
```python
def test_card_audio_rx_jitter_buffer_clamping():
    """Verify _playIncomingPcm16 implements 40ms playhead with 100ms drift packet discard."""
    content = CARD_PATH.read_text(encoding="utf-8")
    body = _extract_js_method(content, "_playIncomingPcm16")
    assert "0.040" in body or "0.04" in body, (
        "_playIncomingPcm16 must target 40ms initial playhead (0.040 or 0.04)"
    )
    assert "0.100" in body or "0.1" in body, (
        "_playIncomingPcm16 must enforce 100ms maximum drift threshold (0.100 or 0.1)"
    )
    assert "return;" in body or "return ;" in body, (
        "_playIncomingPcm16 must discard excess packets exceeding drift threshold before buffer creation"
    )
```

2. Add anti-aliasing filter, sidetone fill(0), and GC cleanup tests:
```python
def test_card_webaudio_lowpass_filter_and_buffer_size():
    """Verify WebAudio TX uses 3400Hz low-pass filter and 1024-sample ScriptProcessor."""
    content = CARD_PATH.read_text(encoding="utf-8")
    tx_fn = _extract_js_method(content, "_startAudioTx")

    assert "createBiquadFilter()" in tx_fn, "_startAudioTx must create a BiquadFilterNode"
    assert '"lowpass"' in tx_fn or "'lowpass'" in tx_fn, "BiquadFilter must be configured as lowpass"
    assert "3400" in tx_fn, "Low-pass cutoff frequency must be set to 3400 Hz for Nyquist anti-aliasing"
    assert "createScriptProcessor(1024" in tx_fn, "ScriptProcessor buffer size must be 1024 samples"


def test_card_microphone_sidetone_isolation():
    """Verify onaudioprocess uses outputData.fill(0) to prevent local echo and resonance."""
    content = CARD_PATH.read_text(encoding="utf-8")
    tx_fn = _extract_js_method(content, "_startAudioTx")

    assert "outputBuffer" in tx_fn, "onaudioprocess must reference outputBuffer"
    assert "outputData.fill(0)" in tx_fn, (
        "onaudioprocess must use outputData.fill(0) to prevent mic loopback to speakers"
    )


def test_card_cleanup_disconnects_audio_nodes_and_clears_callbacks():
    """Verify _cleanupCall disconnects audio source, lowpass filter, and nulls onaudioprocess."""
    content = CARD_PATH.read_text(encoding="utf-8")
    cleanup_fn = _extract_js_method(content, "_cleanupCall")

    assert "this._audioSourceNode" in cleanup_fn, "_cleanupCall must reference _audioSourceNode"
    assert "this._lowpassFilter" in cleanup_fn, "_cleanupCall must reference _lowpassFilter"
    assert "this._scriptProcessor.onaudioprocess = null;" in cleanup_fn, (
        "_cleanupCall must explicitly null onaudioprocess callback to prevent GC leaks"
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
uv run --with pytest pytest tests/test_frontend_and_blueprint.py -k "jitter_buffer_clamping or webaudio_lowpass or sidetone_isolation or cleanup_disconnects" -v
```
Expected: FAIL.

- [ ] **Step 3: Implement WebAudio optimizations in `ave-video44-card.js`**

1. In constructor (lines 15-20):
Add tracking for `this._audioSourceNode = null;` and `this._lowpassFilter = null;`:
```javascript
    this._mediaStream = null;
    this._audioSourceNode = null;
    this._lowpassFilter = null;
    this._audioCtx = null;
    this._audioWorkletNode = null;
    this._scriptProcessor = null;
```

2. In `_startAudioTx()` (lines 1143-1191):
```javascript
  async _startAudioTx() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error("Dispositivo senza supporto WebAudio getUserMedia");
    }

    this._ensureAudioContext();
    if (this._audioCtx && this._audioCtx.state === "suspended") {
      await this._audioCtx.resume();
    }

    this._mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      },
      video: false
    });

    this._audioSourceNode = this._audioCtx.createMediaStreamSource(this._mediaStream);

    // Anti-aliasing Nyquist filter: suppress frequencies above 3400 Hz before 8 kHz resampling
    this._lowpassFilter = this._audioCtx.createBiquadFilter();
    this._lowpassFilter.type = "lowpass";
    this._lowpassFilter.frequency.value = 3400;
    this._lowpassFilter.Q.value = 0.7071;

    // Halve capture buffer to 1024 samples (~21.3ms at 48kHz) to eliminate dual-packet bursts
    const bufferSize = 1024;
    this._scriptProcessor = this._audioCtx.createScriptProcessor(bufferSize, 1, 1);

    const inputSampleRate = this._audioCtx.sampleRate;

    this._scriptProcessor.onaudioprocess = (e) => {
      // Acoustic isolation: zero out output buffer to prevent mic audio leaking into local speakers
      const outputData = e.outputBuffer.getChannelData(0);
      outputData.fill(0);

      if (this._isMuted || !this._inCall || !this._hass) return;
      const inputData = e.inputBuffer.getChannelData(0);
      const pcm16Data = this._resampleTo8kPcm16(inputData, inputSampleRate);

      for (let i = 0; i < pcm16Data.length; i++) {
        this._txAccumulator.push(pcm16Data[i]);
      }

      while (this._txAccumulator.length >= 160) {
        const chunk16 = new Int16Array(this._txAccumulator.splice(0, 160));
        const base64Str = this._arrayBufferToBase64(chunk16.buffer);
        this._hass.connection.sendMessage({
          type: "ave_video44/audio_tx",
          device_id: this._config.device_id,
          payload: base64Str,
          ack: false
        });
      }
    };

    this._audioSourceNode.connect(this._lowpassFilter);
    this._lowpassFilter.connect(this._scriptProcessor);
    this._scriptProcessor.connect(this._audioCtx.destination);
  }
```

3. In `_playIncomingPcm16(pcm16Array)` (lines 1247-1274):
Apply early packet discard BEFORE allocating AudioBuffer/AudioBufferSourceNode:
```javascript
  _playIncomingPcm16(pcm16Array) {
    if (!this._audioCtx || this._audioCtx.state === "closed") return;
    if (this._audioCtx.state === "suspended" && !this._audioResuming) {
      this._audioResuming = true;
      this._audioCtx.resume().catch(() => {}).finally(() => {
        this._audioResuming = false;
      });
    }

    const now = this._audioCtx.currentTime;
    const leadTime = 0.040; // 40ms target playhead
    const maxDrift = 0.100; // 100ms drift threshold

    if (!this._nextScheduledPlayTime || this._nextScheduledPlayTime <= now) {
      this._nextScheduledPlayTime = now + leadTime;
    } else if (this._nextScheduledPlayTime - now > maxDrift) {
      // Packet discard: scarta il frame in eccesso per evitare buffer bloat e sovrapposizioni
      return;
    }

    const buffer = this._audioCtx.createBuffer(1, pcm16Array.length, 8000);
    const channelData = buffer.getChannelData(0);
    for (let i = 0; i < pcm16Array.length; i++) {
      channelData[i] = pcm16Array[i] / 32768.0;
    }

    const source = this._audioCtx.createBufferSource();
    source.buffer = buffer;
    source.connect(this._audioCtx.destination);

    source.start(this._nextScheduledPlayTime);
    this._nextScheduledPlayTime += buffer.duration;
  }
```

4. In `_cleanupCall()` (lines 1276-1318):
Ensure explicit callback clearing and node disconnection:
```javascript
    if (this._mediaStream) {
      this._mediaStream.getTracks().forEach((track) => track.stop());
      this._mediaStream = null;
    }
    if (this._audioSourceNode) {
      this._audioSourceNode.disconnect();
      this._audioSourceNode = null;
    }
    if (this._lowpassFilter) {
      this._lowpassFilter.disconnect();
      this._lowpassFilter = null;
    }
    if (this._scriptProcessor) {
      this._scriptProcessor.onaudioprocess = null;
      this._scriptProcessor.disconnect();
      this._scriptProcessor = null;
    }
```

- [ ] **Step 4: Run tests and JavaScript syntax check**

Run:
```bash
node -c custom_components/ave_video44/frontend/ave-video44-card.js
uv run --with pytest pytest tests/test_frontend_and_blueprint.py -k "jitter_buffer_clamping or webaudio_lowpass or sidetone_isolation or cleanup_disconnects" -v
```
Expected: PASS.

---

### Task 3: Version Bump & Release Notes (v1.3.5)

**Files:**
- Modify: `custom_components/ave_video44/manifest.json`
- Modify: `pyproject.toml`
- Modify: `custom_components/ave_video44/frontend/ave-video44-card.js`
- Modify: `custom_components/ave_video44/__init__.py`
- Modify: `tests/test_repo_governance.py:96-100`
- Modify: `tests/test_frontend_and_blueprint.py:504-508`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: Release identifier `"1.3.5"`.
- Produces: Synchronized SemVer across manifests, scripts, tests, and bilingual release notes.

- [ ] **Step 1: Update version constants across the repository**

1. `custom_components/ave_video44/manifest.json`:
```json
  "version": "1.3.5"
```

2. `pyproject.toml`:
```toml
version = "1.3.5"
```

3. `custom_components/ave_video44/frontend/ave-video44-card.js`:
```javascript
const CARD_VERSION = "1.3.5";
```

4. `custom_components/ave_video44/__init__.py`:
```python
_CARD_VERSION = "1.3.5"
...
resource_url = "/ave_video44_card/ave-video44-card.js?v=1.3.5"
```

5. `tests/test_repo_governance.py`:
Update lines 96-100:
```python
    assert manifest["version"] == "1.3.5"
    assert pyproject["project"]["version"] == "1.3.5"
    match = re.search(r'const\s+CARD_VERSION\s*=\s*"([^"]+)"', card_js)
    assert match is not None
    assert match.group(1) == "1.3.5"
```

6. `tests/test_frontend_and_blueprint.py`:
Update test function and assertion:
```python
def test_card_version_bumped_1_3_5():
    """Verify CARD_VERSION constant is bumped to 1.3.5."""
    content = CARD_PATH.read_text(encoding="utf-8")
    assert 'const CARD_VERSION = "1.3.5";' in content
```

- [ ] **Step 2: Add bilingual release notes in `CHANGELOG.md`**

Prepend the entry under `## [Non rilasciato]` in `CHANGELOG.md`:
```markdown
## v1.3.5 — 2026-10-31

### 🇬🇧 English
- **WebAudio Anti-Aliasing (Voice Nyquist Filter)**: Added a 3400 Hz Butterworth low-pass BiquadFilter before 8 kHz resampling, cutting out high-frequency foldback distortion and eliminating robotic/metallic voice artifacts.
- **Microphone Sidetone Isolation & Clean Teardown**: Cleared `outputBuffer` via `outputData.fill(0)` in `onaudioprocess`, isolating microphone input from browser speaker playback to eliminate local echo and screeching feedback; disconnected `_audioSourceNode` and cleared `onaudioprocess` handler during call cleanup.
- **Low-Latency Chunking & Fire-and-Forget TX**: Reduced `ScriptProcessorNode` buffer to 1024 samples (halving input delay from ~43 ms to ~21 ms and generating single 20 ms frames) and added optional `ack` flag (default `false`) on `ave_video44/audio_tx` to spare 50 unnecessary JSON reply messages per second.
- **Adaptive RX Jitter Buffer with Packet Discard**: Replaced static 120 ms playback latency with an agile 40 ms target playhead and strict 100 ms drift drop threshold with early packet discard before buffer allocation, preventing audio overlap, frame pile-up, and comb filtering.
- **SIP Register Cooldown Resilience**: Extended socket timeout retry sleep on SIP `REGISTER` to 3.0s per Lesson 26, avoiding `ConnectionResetError` on OpenSIPS and TS-SMART 2-wire bus resets while preserving buffer flush and error escalation.

### 🇮🇹 Italiano
- **Anti-Aliasing WebAudio (Filtro Nyquist Vocale)**: Inserito un filtro passa-basso Butterworth a 3400 Hz prima del resampling a 8 kHz, eliminando l'aliasing delle alte frequenze e la voce robotica/metallica.
- **Isolamento Acustico Microfono e Teardown Pulito**: Azzerato l'`outputBuffer` con `outputData.fill(0)` in `onaudioprocess`, separando la cattura microfonica dall'altoparlante del browser ed eliminando completamente eco locale e fischi; disconnesso `_audioSourceNode` e azzerato il gestore `onaudioprocess` in `_cleanupCall`.
- **Chunking a Bassa Latenza e TX Fire-and-Forget**: Ridotto il buffer di `ScriptProcessorNode` a 1024 campioni (dimezzando la latenza di cattura da ~43 ms a ~21 ms ed eliminando le raffiche binate) e introdotto il parametro opzionale `ack` (default `false`) su `ave_video44/audio_tx` risparmiando 50 messaggi JSON/s di riscontro verso il browser.
- **Jitter Buffer Dinamico RX con Packet Discard**: Sostituito il ritardo statico di 120 ms con un playhead reattivo a 40 ms e scarto preventivo pacchetti oltre 100 ms di drift prima dell'allocazione del buffer, prevenendo sovrapposizioni audio, accumuli e comb filtering.
- **Resilienza Cooldown SIP Register**: Esteso lo sleep di retry su timeout del `REGISTER` SIP a 3.0s in conformità alla Lezione 26, prevenendo `ConnectionResetError` sul bus 2-fili TS-SMART e OpenSIPS mantenendo il flush del buffer e la propagazione dell'eccezione terminale.
```

- [ ] **Step 3: Run repository governance tests**

Run:
```bash
uv run --with pytest --with cryptography --with pyyaml pytest tests/test_repo_governance.py tests/test_frontend_and_blueprint.py -k "semver or version_bumped" -v
```
Expected: PASS.

---

### Task 4: Regression & Full Verification Suite

**Files:**
- Suite-wide verification across all test files.

**Interfaces:**
- Consumes: All updated integration components, tests, and documentation.
- Produces: Clean zero-regression test run and style validation.

- [ ] **Step 1: Run comprehensive pytest regression suite**

Run:
```bash
uv run --with pytest --with cryptography --with pytest-asyncio --with pyyaml pytest -q --tb=short --maxfail=2
```
Expected: All 165+ tests PASS.

- [ ] **Step 2: Run Ruff linter check on modified backend files**

Run:
```bash
uv run --with ruff ruff check custom_components/ave_video44/websocket_api.py custom_components/ave_video44/core/sip_session.py tests/test_websocket_api.py tests/test_cloud_sip_video.py tests/test_entities_and_ws.py
```
Expected: Zero lint errors or cleanly formatted imports.

- [ ] **Step 3: Verify zero legacy WebView operator violations in card**

Run:
```bash
python3 -c '
import re, sys
code = open("custom_components/ave_video44/frontend/ave-video44-card.js").read()
code = re.sub(r"/\*[\s\S]*?\*/", "", code)
code = re.sub(r"^\s*//.*$", "", code, flags=re.MULTILINE)
matches = re.findall(r"\?\.[A-Za-z0-9_$([]|\?\?", code)
if matches:
    print("Found forbidden syntax:", matches)
    sys.exit(1)
print("WebView syntax check passed: 0 forbidden operators found")
'
```
Expected: Output `WebView syntax check passed: 0 forbidden operators found`.
