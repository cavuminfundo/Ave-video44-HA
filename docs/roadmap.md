# AVE Video V44 — Project Roadmap & Milestones

> **Target Platform**: AVE Video V44 Intercom Systems (V44 EASY, V44 SMART, GVS)  
> **Target Integration**: Home Assistant Custom Integration (`custom_components/ave_video44`)

---

## Phase 0: Workspace Scaffolding, Governance & Golden Rules (✅ Completed)
- [x] Initial repository structure and workspace doctor verification (`workspace_doctor.py`).
- [x] VCS exclusions: `.gitignore` configured for virtualenvs, caches, build artifacts, and local dumps.
- [x] Archetype classification: `backend` (`python`, `homeassistant`, `frontend`) registered.
- [x] Agent router configuration: `.agents/AGENTS.md` with Ponytail Ladder, Antislop, Zero Secrets, and SDD rules.
- [x] Lessons learned repository initialized: `.agents/memory/lessons.md` with AVE/GVS hardware context.
- [x] CI/CD workflows: GitHub Actions suite configured for HACS validation, Hassfest, Card WebView linting, SemVer guards, and release automation.

---

## Phase 1: Protocol Reverse Engineering & Discovery Specification (✅ Completed)
- [x] Cloud REST endpoints reverse engineering:
  - Base API domain and endpoints mapped (`https://avev2.gvs-icloud.com`).
  - HMAC-SHA1 signature algorithm (`to_encryption`) mapped and implemented.
  - Password hashing (client-side SHA-256) and email OTP login flows verified.
- [x] MQTT Push Plane Analysis:
  - Persistent TLS broker mapped (`eu.emqx.gvs-icloud.com:8883`).
  - Doorbell ring events (`monitoring` action 1) and call end events (action 0) verified.
- [x] Local LAN Protocol Discovery:
  - Local GVS UDP control protocol on port 8300 with 10-byte magic header (`GVSGVS\xa5\xa5\xa5\xa5`).
  - Function codes, command codes, and 6-byte room address structure mapped.
  - SIP signaling (UDP/TCP 5060) and RTP audio/video stream parameters identified.

---

## Phase 2: Core Client Library & Async Networking (✅ Completed)
- [x] Asynchronous Python client implementation (`custom_components/ave_video44/core/`):
  - `api.py`: Async REST client with session injection, HMAC-SHA1 signing, and retry backoff.
  - `protocol.py`: Binary frame encoder/decoder with magic header and room address format.
  - `mqtt.py`: Async MQTT client handling push status events and doorbell ring notifications.
  - `sip_session.py`: SIP session state machine, SIP INFO unlock, and RTP G.711a audio bridge.
- [x] Session lifecycle management:
  - Managed `aiohttp.ClientSession` reuse via `async_get_clientsession(hass)`.
  - Non-blocking I/O with explicit timeouts across all network operations.

---

## Phase 3: Home Assistant Entity Platforms & WebSocket Bridge (✅ Completed)
- [x] Coordinator and Platform Integration:
  - `coordinator.py`: DataUpdateCoordinator correlating cloud polling, MQTT events, and local device state.
  - `camera.py`: Live RTSP stream with snapshot capture.
  - `lock.py`: Independent pedestrian gate (`Lock 1`) and driveway gate (`Lock 2`) control with auto-relock timer.
  - `button.py`: Instant pulse unlock triggers.
  - `event.py`: Doorbell press and call termination events with `doorbell` device class.
  - `binary_sensor.py`: Active call state and network connectivity sensors.
  - `sensor.py`: Intercom call lifecycle state and duration telemetry.
  - `select.py`: Intercom extension directory selector for inter-apartment calls (`HOUSETOHOUSE`).
- [x] Low-Latency WebSocket Audio Bridge:
  - `websocket_api.py`: Bidirectional audio streaming between Lovelace frontend and intercom RTP audio socket.
  - Transcoding pipeline between 8kHz PCM16 (WebSocket) and G.711a A-law (RTP UDP).

---

## Phase 4: Frontend Lovelace Card, Blueprint & Companion Experience (✅ Completed)
- [x] Custom Lovelace Card (`ave-video44-card.js`):
  - High-contrast technical utility theme compliant with WCAG AA.
  - WebAudio microphone capture with real-time 8kHz mono PCM16 downsampling.
  - Zero external npm dependencies.
  - Strict legacy Android WebView compatibility (elimination of `?.` and `??` operators).
  - Automatic Lovelace resource registration via `card_loader.py`.
- [x] Interactive Notification Blueprint (`incoming_call_notification.yaml`):
  - High-priority smartphone push notification with visitor camera snapshot.
  - Interactive notification actions ("Rispondi", "Rifiuta", "Apri Cancello").
  - Instant deep linking (`?ave_call=answer`) to launch hands-free call modal automatically.
  - Optional multi-room TTS voice announcements on smart speakers.

---

## Phase 5: HACS v1.0.0 Release, Field Validation & Future Expansions (Current Focus)
- [x] Version parity synchronization (`1.0.0`) across manifest, pyproject.toml, and card JS.
- [x] Bilingual changelog documentation (`CHANGELOG.md`) and automated GitHub Release workflow.
- [ ] Field verification with live AVE Video V44 physical hardware installations.
- [ ] Future Enhancements:
  - Native `go2rtc` bidirectional WebRTC audio pass-through.
  - Multi-camera video switching for premises with multiple outdoor stations.
  - Elevator relay control integration (`LIFTLINK_FUNCTION = 8`).
  - RFID access card management platform (`CARD_PORT = 8000`).
