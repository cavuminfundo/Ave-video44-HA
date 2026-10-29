# Audio RX Keepalive, Decoder Robustness & Card Tab Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore continuous audio reception (RX) and prevent premature call drops by fixing the UDP keepalive payload, adding robust fallback for plain RTP/SRTP SDP in FFmpeg audio decoder, transferring audio callbacks during session renewal, and removing disruptive auto-hangup on browser tab visibility change.

**Architecture:** 
1. `CloudSipMediaSession`: replace corrupt H.264 video dummy packets on audio UDP socket with valid audio RTP/SRTP silence or eliminate unneeded audio hole-punching packets once NAT is open; make `_generate_audio_sdp` support both `RTP/SAVP` (with crypto) and `RTP/AVP` (without crypto if `callee_audio_key` is empty); add explicit debug logging for FFmpeg audio spawn.
2. `AveVideo44Coordinator`: in `async_commit_session`, copy `_rx_pcm16_callbacks` from `old_sess` to `new_session` so browser WebSocket subscribers continue receiving audio after 40s pre-renewals.
3. `AveVideo44Card`: in `_handleVisibilityChange`, call `this._stopFramePolling()` when `document.hidden` is true, but NEVER call `this._hangup()` automatically. Terminate calls only on explicit user hangup button click, Escape key, or remote BYE.
4. `Governance`: synchronize SemVer to `1.3.2` across `manifest.json`, `pyproject.toml`, `ave-video44-card.js`, and `CHANGELOG.md`.

**Tech Stack:** Python 3.12+, Home Assistant Core, `asyncio`, WebAudio API, vanilla Custom Web Component, ITU-T G.711u/a, RFC 3711 SRTP.

**Spec / Empirical Evidence:**
- Empirically observed in Home Assistant core logs at 09:31:28 and 09:33:00–09:33:52:
  - `audio rx pkts=18` and `audio rx pkts=31`: audio packets arrived initially, but stopped after `dummy_rtp` (PT 96 H.264) was sent to `remote_audio_port`.
  - At 09:31:28: `Hanging up call/monitoring on device 677771932745207808` triggered within 900ms of audio subscribe due to `_handleVisibilityChange` calling `this._hangup()`.
  - At 09:33:43: `mjpeg session renewed after remote BYE n=1` committed `new_sess` without copying `_rx_pcm16_callbacks`.

## Global Constraints
- Pure Python G.711u/a and RFC 3711 cryptography. Zero usage of deprecated `audioop`.
- Strict WebView legacy compatibility in `ave-video44-card.js`: zero optional chaining (`?.`) and zero nullish coalescing (`??`).
- Zero plaintext secrets in logs or code.
- Antislop comment hygiene: no ceremonial box drawings, banners, or decorative emojis.
- Maximum 1 line inline edit for Master Agent; all implementation delegated to subagents.

---

### Domain Skills & Sub-Agent Roster (N-Domain Mapping)
1. **Domain: Backend Audio & SIP Protocol**
   - Companion: `ponytail` (/home/federico/skills_library/ponytail/SKILL.md)
   - Worker Type: `backend_audio_worker` (`Model: 'flash'`)
   - Exclusive files: `custom_components/ave_video44/core/sip_session.py`, `custom_components/ave_video44/coordinator.py`, `tests/test_cloud_sip_audio.py`
2. **Domain: Frontend Card UX & Lifecycle**
   - Companion: `antislop-ui` (/home/federico/skills_library/antislop-ui/SKILL.md)
   - Worker Type: `frontend_audio_worker` (`Model: 'flash'`)
   - Exclusive files: `custom_components/ave_video44/frontend/ave-video44-card.js`, `tests/test_frontend_and_blueprint.py`
3. **Domain: Governance & Release**
   - Companion: `ponytail` (/home/federico/skills_library/ponytail/SKILL.md)
   - Worker Type: `governance_worker` (`Model: 'flash'`)
   - Exclusive files: `custom_components/ave_video44/manifest.json`, `pyproject.toml`, `custom_components/ave_video44/__init__.py`, `tests/test_repo_governance.py`, `CHANGELOG.md`

---

## Tasks

### Task 1: Backend Audio Keepalive & Robust SDP Fallback

**Files:**
- Modify: `custom_components/ave_video44/core/sip_session.py:680-705, 1100-1135, 1555-1575`
- Test: `tests/test_cloud_sip_audio.py`

**Interfaces:**
- Consumes: `CloudSipMediaSession`, `parse_200_ok_sdp`
- Produces: `_generate_audio_sdp(ffmpeg_audio_port, crypto_suite, crypto_key, payload_type)` supporting empty `crypto_key` (plain `RTP/AVP`), audio-specific dummy/keepalive or omitting corrupt video packets on audio port, and debug log on FFmpeg audio spawn.

- [ ] **Step 1: Write failing tests in `tests/test_cloud_sip_audio.py`**
  Add tests:
  1. `test_cloud_sip_media_session_generate_audio_sdp_plain_rtp()`:
     Verify that when `crypto_key=""`, `_generate_audio_sdp` emits `m=audio {port} RTP/AVP {pt}` without `a=crypto:`.
  2. `test_cloud_sip_media_session_audio_keepalive_payload_type()`:
     Verify that `_udp_relay_loop` does NOT send H.264 video payload (PT 96) to `remote_audio_port`. If audio keepalive is sent, verify it matches audio payload type (PT 0 or 8) or comfort noise.
  3. `test_cloud_sip_media_session_ffmpeg_audio_spawn_plain_rtp()`:
     Verify that `async_start` starts FFmpeg audio subprocess even if `callee_audio_key` is empty, using `RTP/AVP`.
  4. `test_cloud_sip_media_session_mjpeg_high_quality_qscale()`:
     Verify that `ffmpeg_cmd` in `async_start` uses `-q:v 2` (high-definition crisp JPEG encoding) instead of `-q:v 6`.

- [ ] **Step 2: Run test to verify it fails**
  Run: `uv run --with pytest --with cryptography --with pyyaml pytest tests/test_cloud_sip_audio.py -k "plain_rtp or audio_keepalive or high_quality" -v`
  Expected: FAIL

- [ ] **Step 3: Implement minimal backend changes in `sip_session.py`**
  - In `_generate_audio_sdp`: if `crypto_key` is non-empty, use `RTP/SAVP` with `a=crypto:1 {crypto_suite} inline:{crypto_key}`. If `crypto_key` is empty, use `RTP/AVP` and omit `a=crypto:`.
  - In `_udp_relay_loop`: do NOT send `dummy_rtp` (video PT 96) on `_audio_sock`. Instead, if `self._audio_sock and remote_audio_port`, send valid audio silence/comfort frame or skip sending to prevent proxy corruption.
  - In `async_start`: remove the requirement that `callee_audio_key` must be non-empty to start audio FFmpeg. Start audio FFmpeg whenever `self.enable_audio and self._ffmpeg_audio_port` is true. Log the audio FFmpeg spawn command at `_LOGGER.debug`.
  - In `async_start`: update `ffmpeg_cmd` to set `-q:v 2` for high JPEG definition and edge sharpness.

- [ ] **Step 4: Run test to verify it passes**
  Run: `uv run --with pytest --with cryptography --with pyyaml pytest tests/test_cloud_sip_audio.py -v`
  Expected: PASS

---

### Task 2: Coordinator Audio Callback Persistence across Session Renewals & Cloud HD Monitoring

**Files:**
- Modify: `custom_components/ave_video44/coordinator.py:313-320, 555-590`
- Test: `tests/test_cloud_sip_audio.py`

**Interfaces:**
- Consumes: `AveVideo44Coordinator.async_commit_session`, `control_monitoring`
- Produces: callback preservation from `old_sess._rx_pcm16_callbacks` into `new_session._rx_pcm16_callbacks`, and `resolution_level=1` (HD) request on camera monitoring start.

- [ ] **Step 1: Write failing test in `tests/test_cloud_sip_audio.py`**
  Add test `test_coordinator_commit_session_preserves_rx_callbacks()`:
  Create mock `old_sess` with a registered RX callback in `_rx_pcm16_callbacks`, call `async_commit_session(device_id, new_sess)`, and assert that `new_sess._rx_pcm16_callbacks` contains the callback.
  Add test `test_coordinator_monitoring_requests_hd_resolution()`:
  Verify `control_monitoring` is invoked with `resolution_level=1`.

- [ ] **Step 2: Run test to verify it fails**
  Run: `uv run --with pytest --with cryptography --with pyyaml pytest tests/test_cloud_sip_audio.py -k "commit_session_preserves or requests_hd" -v`
  Expected: FAIL

- [ ] **Step 3: Implement minimal changes in `coordinator.py`**
  In `async_commit_session`:
  ```python
  if old_sess and hasattr(old_sess, "_rx_pcm16_callbacks") and hasattr(new_session, "add_rx_pcm16_callback"):
      for cb in list(old_sess._rx_pcm16_callbacks):
          new_session.add_rx_pcm16_callback(cb)
  ```
  In `async_wake_camera`:
  Set `resolution_level=1` in `control_monitoring` call.

- [ ] **Step 4: Run test to verify it passes**
  Run: `uv run --with pytest --with cryptography --with pyyaml pytest tests/test_cloud_sip_audio.py -k "commit_session_preserves or requests_hd" -v`
  Expected: PASS

---

### Task 3: Frontend VisibilityChange & Audio Lifecycle Fix

**Files:**
- Modify: `custom_components/ave_video44/frontend/ave-video44-card.js:186-194`
- Test: `tests/test_frontend_and_blueprint.py`

**Interfaces:**
- Consumes: `_handleVisibilityChange()`
- Produces: tab backgrounding pauses frame polling (`_stopFramePolling()`), but NEVER triggers `_hangup()`.

- [ ] **Step 1: Write failing test in `tests/test_frontend_and_blueprint.py`**
  Add test `test_card_visibility_change_does_not_hangup_call()`:
  Verify that `_handleVisibilityChange` in `ave-video44-card.js` does NOT call `this._hangup()`.
  Verify that when `document.hidden` is true, `_stopFramePolling()` is called, keeping `_inCall` intact.

- [ ] **Step 2: Run test to verify it fails**
  Run: `uv run --with pytest pytest tests/test_frontend_and_blueprint.py -k "visibility_change" -v`
  Expected: FAIL

- [ ] **Step 3: Implement minimal change in `ave-video44-card.js`**
  Update `_handleVisibilityChange`:
  ```javascript
  _handleVisibilityChange() {
    if (document.hidden) {
      this._stopFramePolling();
    } else if (this._inCall) {
      this._startFramePolling(true);
    }
  }
  ```

- [ ] **Step 4: Run test to verify it passes**
  Run: `uv run --with pytest pytest tests/test_frontend_and_blueprint.py -v`
  Expected: PASS

---

### Task 4: Governance, SemVer 1.3.2 & Release Notes

**Files:**
- Modify: `custom_components/ave_video44/manifest.json`
- Modify: `pyproject.toml`
- Modify: `custom_components/ave_video44/frontend/ave-video44-card.js` (CARD_VERSION = "1.3.2")
- Modify: `custom_components/ave_video44/__init__.py` (v=1.3.2)
- Modify: `tests/test_repo_governance.py`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Update version numbers to 1.3.2 across all files**
- [ ] **Step 2: Document bugfixes in `CHANGELOG.md` under `## v1.3.2 — 2026-10-29` in Italian and English**
- [ ] **Step 3: Run repository governance tests**
  Run: `uv run --with pytest pytest tests/test_repo_governance.py -v`
  Expected: PASS

- [ ] **Step 4: Run full test suite**
  Run: `uv run --with pytest --with cryptography --with pyyaml pytest -q --tb=short --maxfail=2`
  Expected: 140+ PASS
