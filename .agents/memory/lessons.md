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
  - Cloud endpoints require a double-Base64 HMAC-SHA1 signature (`compute_gvs_sign` / `StringUtil.toEncryption`).
  - Query parameters are sorted alphabetically by key (excluding `sign` and null values), concatenated with `&`, pre-encoded to Base64, hashed with HMAC-SHA1 using `appSecret`, and converted to lowercase Base64: `base64(HMAC-SHA1(secret, base64(sorted_query_string))).lower()`.
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

---

## 2026-10-25 — Cloud API v2.1.2 Alignment & Home Assistant 2025/2026 Invariants

### 6. AVE/GVS Double-Base64 HMAC-SHA1 Signature (`compute_gvs_sign`)
- **Root Cause & Discovery**: Decompilation of the official AVE Android APK v2.1.2 (`StringUtil.toEncryption`) revealed that the sorted query string (`k1=v1&k2=v2`) is encoded in Base64 *before* being passed into the HMAC-SHA1 digest function.
- **Formula**: `base64(HMAC-SHA1(secret, base64(sorted_query_string))).lower()`
- **Trap**: Hashing the plaintext query string directly causes the server to reject calls with HTTP 401/403 "signature error" or "invalid signature".

### 7. Retrofit QueryMap / FieldMap Split & JSON Envelopes
- **Parameter Split on Login**: In `POST /usercenter/api/uc/loginToGvs/email`, common auth parameters (`tenantUuid`, `appUuid`, `ts`, `sign`) are sent as URL query parameters (`@QueryMap`), while user credentials (`account`, `password`, `channel` or `email`, `code`) are sent in the form-urlencoded POST body (`@FieldMap`).
- **Response Envelope**: AVE/GVS endpoints wrap payloads in `"result"` rather than standard `"data"` (e.g. `{"code": 200, "result": {...}}`). Response parsers must fall back gracefully across `resp.get("result") or resp.get("data")`.
- **Session Cookie Persistence**: In addition to `token` and `sessionId` headers, `JSESSIONID` from `Set-Cookie` must be maintained for subsequent calls (`queryHomeList`, `user-current-home`, `device/getInfo`).

### 8. Home Assistant 2025/2026 `OptionsFlow.config_entry` Read-Only Invariant
- **Hazard**: Starting in Home Assistant Core 2024.11 / 2025+, `OptionsFlow.config_entry` is declared as a read-only `@property` without a setter.
- **Root Cause**: Subclasses that execute `self.config_entry = config_entry` in `__init__` raise `AttributeError: property 'config_entry' of 'AveVideo44OptionsFlow' object has no setter`, breaking the Configure options modal entirely.
- **Fix**: Never assign `self.config_entry`. Rely on Home Assistant's automatic entry assignment via `async_get_options_flow` and access `self.config_entry` directly through the inherited property.

---

## 2026-10-25 — v1.1.0 Guided OptionsFlow, Entity Registry Migrations & Zero-YAML Lovelace Card

### 9. Zero-YAML Lovelace Card Resource Injection & Browser Cache Busting
- **Zero-YAML Registration**: Using Home Assistant's `add_extra_js_url(hass, f"/ave_video44_frontend/ave-video44-card.js?v={VERSION}")` directly via `card_loader.py` during entry setup eliminates the requirement for users to manually add resources in Lovelace dashboard settings.
- **Cache-Busting Invariant**: Browsers aggressively cache static JavaScript resources. Without an explicit version query parameter (`?v=1.1.0`), users upgrading custom integrations frequently experience cached older script evaluations, missing new editor features or protocol fixes. Always append `?v={VERSION}`.
- **Visual Editor Registration**: Exposing `window.customCards` metadata along with `getConfigElement()` and `getStubConfig(hass)` enables seamless card discovery in the Home Assistant dashboard UI card picker with automatic entity preselection.

### 10. Entity Registry Disabled-by-Default Policy for Redundant Control Entities
- **Dashboard Clutter Prevention**: When an integration provides multiple entity representations for the same physical actuator (such as `lock.posto_esterno_cancelletto_pedonale` with state feedback vs `button.apri_cancelletto` for instant pulses), exposing both by default clutters automatically generated Lovelace dashboards.
- **Entity Registry Flag**: Setting `_attr_entity_registry_enabled_default = False` on the button entity keeps the primary control (`lock`) active while leaving the secondary trigger (`button`) available in the Entity Registry for users who explicitly require stateless pulse buttons or shortcut buttons.
- **Non-Destructive for Existing Users**: In Home Assistant, `_attr_entity_registry_enabled_default` is evaluated only during initial entity registration; it does not unexpectedly disable entities for existing users who already configured them.

### 11. Guided Interactive OptionsFlow Architecture & Default Dropdown Fallbacks
- **User Experience in Multi-Entry Config**: Asking users to write raw comma-separated `code=label` strings in single text fields is error-prone. Providing a multi-step guided OptionsFlow (menu -> add/edit contact -> remove contact -> general settings) eliminates syntax errors and provides instant validation.
- **Single-Click Removal**: Providing a dropdown populated with existing contact keys for the `remove_contact` step allows clean removal without requiring manual string manipulation or regex parsing by the user.
- **Empty State Fallback**: When no contacts are configured, populating `select.rubrica_interni` with a disabled/default choice (`Nessun interfono configurato`) prevents Lovelace select cards from crashing or rendering blank unpopulated dropdowns.

---

## 2026-10-25 — v1.2.0 RTSPS Cloud Stream, Bubble Card UI, Camera Wake Lifecycle & Sidebar Dashboard

### 12. 2-Wire Doorstation Physical Energy Management & Cloud Camera Wake Lifecycle
- **Physical Invariant**: In 2-wire bus video intercom systems (e.g. AVE `VI2F` / `TS-SMART`), the outdoor doorstation camera and DSP are physically powered down when idle to preserve bus power and thermal limits. Attempting to open the RTSP stream in idle yields `Connection refused`.
- **API Wake & Teardown**: Calling `POST /smarthome/api/device-monitoring/monitoring` with `action=1` (`monitoringDeviceNumber="1"`) powers up the camera, provisions the active session `callId`, and establishes the live stream. When closing the session, sending `action=3` is mandatory; sending `action=0` fails with cloud error `-1000000400`.
- **Dynamic Camera Stream Capability**: Expose `CameraEntityFeature.STREAM` and valid RTSP URLs only when `call_state` is `ringing`, `talking`, or `monitoring`; return `None` when idle to prevent stream workers from failing repeatedly.

### 13. Mobile Companion App WebView Cache Bypass & Storage Resource Registration
- **Trap**: Mobile WebViews (iOS WKWebView and Android WebView in Home Assistant Companion App) and Service Workers cache static assets aggressively when served with HTTP caching headers. Query parameters like `?v=1.1.0` are frequently ignored by WebViews if the path segment was previously cached with long-lived max-age headers.
- **Fix**: Changing the path prefix (e.g., from `/ave_video44_frontend/` to `/ave_video44_card/ave-video44-card.js`) with `cache_headers=False` completely busts the stale WebView cache.
- **Lovelace Storage Resource Invariant**: In addition to `add_extra_js_url`, programmatically registering the card resource as `res_type: "module"` in `hass.data["lovelace"].resources` ensures the card is recognized across all dashboard types, including storage and YAML modes.

### 14. Intercom Address Book Auto-Discovery & Startup Seeding
- **Discovery Sources**: Device rosters (`quick-display-device/user-current-home`) contain rich metadata: `extraConfig` holds doorstation relay mappings (`deviceNumber`, `deviceName`), and `deviceIntercomInfo` contains extension codes (`haZone`, `username`).
- **Zero-Friction Seeding**: Auto-populating `intercom_book` on startup when empty provides immediate plug-and-play functionality for `select.rubrica_interni` and the Lovelace card without requiring user intervention, while `auto_discover` in `OptionsFlow` provides a 1-click refresh mechanism.

### 15. Cloud TLS RTSPS Streaming & FFmpeg MJPEG Proxy Invariants
- **Port and Auth Split**: AVE/GVS cloud streaming provides RTSPS endpoints over port 8322 (`ports.rtsps: 8322`) requiring cloud basic authentication credentials (`auth.basic.username`, `auth.basic.password`).
- **Dynamic Session Synchronization**: The server path `/stream/1/{deviceId}/0/{targetNum}` or MQTT `"code": "monitoring"` `serverUrl` must be dynamically resolved when `call_state` transitions into `monitoring` or `ringing`.
- **FFmpeg Stream Proxying**: Calling `async_camera_image` or `handle_async_mjpeg_stream` when the camera is powered down causes FFmpeg subprocesses to continuously fail and generate connection refused error logs. Explicitly returning `None` when `stream_source()` is `None` ensures clean Home Assistant logs while still allowing instant on-demand proxying when active.

### 16. Bubble Card UI Design, Customizable Title & Responsive Panel Constraints
- **Visual Ergonomics**: Standard HA Lovelace cards often look rigid. Implementing Bubble Card conventions (pill containers with `border-radius: 28px`, circular icon bubbles inside full-pill buttons `.bubble-pill-btn`, floating state badge) creates an intuitive, tactile experience on mobile and touchscreens.
- **Customizable Title Invariant**: Exposing `config.title` both in YAML and in `getConfigElement()` (`ave-video44-card-editor`) gives users full control over dashboard branding while defaulting sensibly to `"AVE Video V44"`.
- **Panel Mode Overflow Guard**: In full panel dashboards (`type: "panel"`), elements can stretch excessively on ultra-wide desktop monitors. Clamping the card container to `max-width: 780px` with `margin: 0 auto` and `repeat(auto-fit, minmax(200px, 1fr))` ensures aesthetic balance across all form factors.

---

## 2026-10-25 — v1.2.1 Lovelace hui-panel-view Cold Reload & Idle Viewport Guard

### 17. Lovelace hui-panel-view Cold Reload Limitation & Rebuild Reliability
- Cold Reload Timing Hazard: In Home Assistant Lovelace dashboards configured with `panel: true` (`hui-panel-view`), hard browser reloads (F5) can fail to re-render custom cards if the JS bundle loads after the initial layout render, as `hui-panel-view` does not always subscribe to or bubble the standard `ll-rebuild` event.
- Fix: Use a standard Lovelace view with single-card desktop width expansion (`max-width: 780px`, `margin: 0 auto`). This ensures Home Assistant's standard view reconciler fires `ll-rebuild` whenever custom element definitions settle, eliminating the "Elemento personalizzato inesistente" warning.
- Non-Blocking Storage Sync: Dashboard JSON generation in `.storage/lovelace_dashboards` should always run inside `hass.async_add_executor_job` to avoid blocking Home Assistant's main event loop during disk writes.

### 18. Frontend isVideoActive Guard & Idle Viewport Placeholder
- Standby Camera Power-Down: Because 2-wire outdoor cameras are physically unpowered when idle, loading a camera image snapshot during idle states is invalid.
- Viewport State Coordination: Always guard image and video element visibility with an explicit `isVideoActive` check (`call_state !== "idle"`). Without this check, image error/load callbacks can hide `#videoPlaceholder`, leaving a blank black box instead of the standby background.
- Direct Viewport Interaction: Providing a wake bubble button directly inside the idle `#videoPlaceholder` improves tactile usability by allowing users to tap the screen directly to start monitoring.

---

## 2026-10-25 — v1.2.2 Cloud SIP/SRTP H.264 Video Engine & MQTT Port 18883

### 19. 2-Wire TS-SMART Cloud SIP Architecture (protocol="0")
- Invariant: 2-wire indoor monitors (VI2F-PIT7WF, TS-SMART) reporting protocol="0" do not support RTSPS streaming on port 8322. Live video requires direct SIP INVITE signaling to eu.open-sips.gvs-icloud.com:5060.
- Mandatory Custom Headers: The SIP INVITE must include all 14 proprietary GVS/AVE headers, specifically enableVideo: 1, proxyDeviceId, and proxyFlag: 1. Omitting enableVideo: 1 causes the server to negotiate audio-only or reject with 488.
- SRTP & Symmetric NAT Hole-Punching: The media stream requires RTP/SAVP with AES_CM_128_HMAC_SHA1_80. Stateful NAT firewalls block incoming video packets unless an initial dummy probe packet is sent from the local UDP socket to the remote media endpoint upon 200 OK receipt.

### 20. Cloud MQTTS Port 18883 & Plant-Level Topic Subscriptions
- Port Invariant: The secure TLS port for the AVE/GVS EMQX broker is 18883.
- Topic Hierarchy: In addition to device-specific topics (smarthome/device/{deviceId}), the integration must subscribe to plant-level topics smarthome/device/{homeId} and smarthome/device/status/{homeId} to guarantee event capture across all indoor monitors and doorstations.

---

## 2026-10-25 — v1.2.3 Home Assistant Core MJPEG Boundary, Stream Sync & 2-Wire Local Bus Directory

### 21. Home Assistant Core Camera Proxy MJPEG Boundary & Wake Synchronization
- Core Boundary Invariant: Home Assistant's camera proxy component (`/api/camera_proxy_stream`) expects MJPEG streams to adhere strictly to `Content-Type: multipart/x-mixed-replace; boundary=--frameboundary`. Using non-matching boundary strings such as `boundary=--frame` causes the Core camera proxy stream handler to misparse part boundaries or fail with decoding errors.
- Wake Handshake Race Condition: When triggering on-demand camera wake ("Attiva Video") from custom Lovelace cards, requesting `/api/camera_proxy_stream` before the Cloud SIP/SRTP session completes its handshake results in an immediate `HTTP 502 Bad Gateway`. Implementing an asynchronous synchronization barrier (`async_wait_for_wake`) holds the camera proxy worker until the SIP session establishes and the initial JPEG frame is buffered.
- RTSPS Control Exclusion: Dispatching `POST /smarthome/api/device-monitoring/control-monitoring` (designed for RTSPS on port 8322) is redundant and invalid for 2-wire Cloud SIP systems (`protocol="0"`), as the SIP `INVITE` dialog itself provisions and powers up the doorstation camera stream.

### 22. 2-Wire Bus Local Extension Addressing vs Cloud Community Roster
- Community Status Invariant: In standalone residential installations, the AVE/GVS cloud REST API returns `associatedCommunityStatus: -1` when indoor monitors are not registered to an enterprise multi-tenant cloud community. In this configuration, extension numbers (such as `001-0002` and `001-0004`) exist solely on the local 2-wire hardware bus rather than the cloud database.
- Self-URI Filtering: Intercom auto-discovery must filter out the indoor monitor's own SIP proxy URI to prevent confusing self-calling loopback options in `select.rubrica_interni`. Local bus extension codes must be preserved in the address book for direct `HOUSETOHOUSE` intercom calling.







