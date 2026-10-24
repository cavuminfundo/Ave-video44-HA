# AVE Video V44 Lessons Learned & Operational Knowledge Base

> **Metadata**:
> - **Workspace:** AVE Video V44 (`custom_components/ave_video44`)
> - **Target Hardware:** AVE Video V44 (VI2F-PIT7WF, TS-SMART7, TS-SMART10, GVS doorstations)
> - **Cloud Ecosystem:** AVE / GVS Cloud (`avev2.gvs-icloud.com`, `eu.emqx.gvs-icloud.com:8883`)
> - **Protocol Archetype:** Hybrid Cloud REST/MQTT & Local LAN UDP 8300 / SIP 5060 / RTSP 554
> - **Initialized:** 2026-10-24

---

## 2026-10-24 — Initial Platform Discovery & Governance Setup

### 1. HACS Direct Repository Download (`content_in_root: false`)
- **Direct Fetch Model**: In `hacs.json`, configuring `"content_in_root": false` and omitting `zip_release` enables HACS to clone or download the `custom_components/ave_video44` tree directly from Git repository tags or default branch.
- **Eliminating Release Asset Flakiness**: Avoids reliance on GitHub Release zip assets (`ave_video44.zip`), eliminating asset upload race conditions and ensuring that users always download the exact component structure verified by CI.

### 2. AVE Cloud & Local Protocol Framing Invariants
- **Local GVS UDP Framing (Port 8300)**:
  - Magic Header: 10 fixed bytes `47 56 53 47 56 53 A5 A5 A5 A5` (`b"GVSGVS\xa5\xa5\xa5\xa5"`).
  - Packet Structure: Magic (10B) + Length (uint16_be) + Function ID (1B) + Command ID (1B) + Source DevType (1B) + Source Room (6B) + Dest DevType (1B) + Dest Room (6B) + Payload + CRC16.
  - Room Address Format: 6-byte tuple `[building, staircase, floor, room, sub, res]`.
- **Local Stream & Socket Framing**:
  - Local stream signaling and event reporting uses standard `0x02 ... 0x03` boundary framing and 4-byte big-endian binary length headers.
- **Cloud REST API Signing (`https://avev2.gvs-icloud.com/`)**:
  - Cloud endpoints require an HMAC-SHA1 signature (`to_encryption`).
  - Query parameters must be sorted alphabetically by key (excluding `sign` and null values), concatenated with `&`, signed with `appSecret`, and output as lowercase Base64 string.
- **MQTTS Push Listener (`eu.emqx.gvs-icloud.com:8883`)**:
  - Doorbell events arrive on `smarthome/device/{deviceId}` and `smarthome/device/status`.
  - Action `1` indicates incoming ring (`CALL_IN`), action `0` indicates call hangup or timeout.

### 3. WebAudio 8kHz PCM16 Resampling & Android WebView Legacy Syntax
- **Hardware DSP Invariant**: AVE/GVS intercom hardware DSP operates exclusively on 8000 Hz mono G.711a (PCMA) audio.
- **Frontend Resampling Engine**: Web browsers capture microphone audio at native sampling rates (44.1kHz or 48kHz). The bundled Lovelace card (`ave-video44-card.js`) downsamples the audio buffer to 8000 Hz 16-bit mono PCM (PCM16 little-endian) before dispatching binary WebSocket frames to Home Assistant.
- **Android WebView Legacy Syntax Compatibility**:
  - Wall-mounted tablets and older Android devices running Home Assistant Companion App frequently use Chromium WebView versions that lack support for ES2020+ operators (optional chaining `?.` and nullish coalescing `??`).
  - Using `?.` or `??` causes silent script parse failures, rendering the card element blank without useful console diagnostics.
  - Always use explicit logical checks (`a && a.b ? a.b : c`) in frontend assets to ensure 100% compatibility across all wall panels.

### 4. Hassfest Key Ordering Policy
- Home Assistant's `hassfest` integration validator enforces strict ordering in `custom_components/ave_video44/manifest.json`:
  - `domain` must be first.
  - `name` must be second.
  - All subsequent keys (`codeowners`, `config_flow`, `dependencies`, `documentation`, `iot_class`, `issue_tracker`, `requirements`, `version`) must be in strict alphabetical order.
  - Failure to respect this order causes immediate Hassfest CI failure.

### 5. Isolated Pytest Execution & Sub-Agent Test Ban
- Automated tests should be invoked using `uv run --with pytest pytest -q --tb=short --maxfail=2`.
- Sub-agents are strictly forbidden from running test suites to prevent uncoordinated runs, race conditions, or polluting local environments with untracked lock files.
