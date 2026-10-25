# AVE Video V44 — Architectural Vision & System Design

> **Target Integration**: Home Assistant Custom Integration (`custom_components/ave_video44`)  
> **Hardware Ecosystem**: AVE Video V44 / GVS Intercom (V44 EASY, V44 SMART, `VI2F-PIT7WF`, `TS-SMART7xx`, `TS-SMART10xx`, and GVS outdoor doorstations)  
> **Upstream Platform**: Guangzhou Video-Star Electronics Co., Ltd. (GVS) / AVE Cloud  
> **Archetype**: Backend (`python`, `homeassistant`, `frontend`)

---

## 1. High-Level Architecture

The `ave_video44` integration implements a hybrid architecture combining cloud event push with low-latency local area network (LAN) communication. It bridges AVE Video V44 video intercom systems into Home Assistant with live RTSP video, full-duplex WebAudio voice communication, dual-lock pulse actuation, and automated mobile notifications.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Home Assistant Core                             │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                  custom_components/ave_video44                   │  │
│  │                                                                  │  │
│  │  ┌──────────────┐   ┌───────────────────────┐   ┌─────────────┐  │  │
│  │  │ config_flow  │   │ DataUpdateCoordinator │   │websocket_api│  │  │
│  │  └──────┬───────┘   └───────────┬───────────┘   └──────┬──────┘  │  │
│  │         │                       │                      │         │  │
│  │  ┌──────┴───────────────────────┴──────────────────────┴──────┐  │  │
│  │  │ Core Engine (core/)                                        │  │  │
│  │  │ - api.py: REST HTTPS (HMAC-SHA1 signing, session reuse)    │  │  │
│  │  │ - mqtt.py: TLS MQTTS Push Listener (:18883)                │  │  │
│  │  │ - protocol.py: GVS UDP 8300 Binary Framing Engine          │  │  │
│  │  │ - cloud_sip.py: Cloud SIP + SRTP H.264 Video Engine        │  │  │
│  │  │ - sip_session.py: Local SIP 2.0 Signaling & RTP Bridge     │  │  │
│  │  └──────────────────────────────┬─────────────────────────────┘  │  │
│  │                                 │                                │  │
│  │  ┌──────────────────────────────┴─────────────────────────────┐  │  │
│  │  │ Entities: camera, lock, button, event, binary_sensor,      │  │  │
│  │  │           sensor, select, diagnostics                      │  │  │
│  │  └────────────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────┬──────────────────────────────┬────────┘  │
│                             │                              │           │
│                             │ WebSocket PCM16 / MJPEG      │           │
│                             ▼                              │           │
│  ┌──────────────────────────────────────────────────┐      │           │
│  │ Frontend: ave-video44-card.js (Lovelace Card)    │      │           │
│  │ - Zero-YAML auto-registration (add_extra_js_url) │      │           │
│  │ - AveVideo44CardEditor visual card editor        │      │           │
│  │ - WebAudio 8kHz mono PCM16 Resampling Engine     │      │           │
│  │ - WebRTC / RTSP live video player & call modal   │      │           │
│  └──────────────────────────────────────────────────┘      │           │
└─────────────────────────────┼──────────────────────────────┼───────────┘
                              │                              │
       HTTPS / MQTTS :18883   │                              │ UDP 8300 / Cloud SIP :5060 / SRTP
       (Cloud Push & REST)    │                              │ (Local LAN Control & Cloud Media)
                              ▼                              ▼
┌──────────────────────────────────────┐  ┌──────────────────────────────┐
│          AVE / GVS Cloud             │  │   Local LAN Intercom Bus     │
│   (avev2.gvs-icloud.com / EMQX)      │  │ (Outdoor Stations & Monitors)│
└──────────────────────────────────────┘  ┌──────────────────────────────┘
```

---

## 2. Directory Layout & Subsystem Responsibilities

```
custom_components/ave_video44/
├── __init__.py                ← Entry setup, service registration, platform forwarding
├── manifest.json              ← Integration metadata, dependencies, Hassfest schema
├── const.py                   ← Domain constants, default timeouts, event types
├── config_flow.py             ← UI setup flow (Password SHA256 & OTP) and guided OptionsFlow wizard
├── coordinator.py             ← DataUpdateCoordinator managing polling & MQTT dispatching
├── entity.py                  ← Base entity classes with common DeviceInfo bindings
├── camera.py                  ← Camera entity with instant MJPEG streaming & snapshot preview
├── lock.py                    ← Lock entities (pedestrian & driveway) with auto-relock
├── button.py                  ← Instant pulse unlock action buttons (disabled by default)
├── event.py                   ← Doorbell call events (doorbell_press, answered, missed)
├── binary_sensor.py           ← Call in progress and online connectivity sensors
├── sensor.py                  ← Call state (idle, ringing, talking) and duration sensors
├── select.py                  ← Intercom address book extension selector (HOUSETOHOUSE)
├── diagnostics.py             ← Redacted diagnostics export for sanitized troubleshooting
├── websocket_api.py           ← HA WebSocket commands for audio streaming & call control
├── services.yaml              ← Service call descriptions (call_intercom, unlock)
├── core/
│   ├── __init__.py            ← Core module namespace
│   ├── api.py                 ← Async REST client with HMAC-SHA1 request signing
│   ├── mqtt.py                ← Async MQTTS client listening on eu.emqx.gvs-icloud.com:18883
│   ├── protocol.py            ← GVS binary protocol framing (magic header GVSGVS\xa5\xa5\xa5\xa5)
│   ├── sip_session.py         ← Local SIP 2.0 user agent & RTP PCMA audio bridge
│   └── cloud_sip.py           ← Cloud SIP + SRTP H.264 Video Engine (CloudSipMediaSession)
├── frontend/
│   ├── ave-video44-card.js    ← Custom Lovelace card with WebAudio 8kHz resampling & visual editor
│   └── card_loader.py         ← Automatic Lovelace resource registration handler (add_extra_js_url)
├── blueprints/
│   └── automation/
│       └── incoming_call_notification.yaml ← Push notification & TTS automation blueprint
├── translations/
│   ├── en.json                ← English strings for config flow and entity titles
│   └── it.json                ← Italian strings for config flow and entity titles
└── brand/
    ├── icon.png               ← HACS / Home Assistant brand icon
    └── logo.png               ← HACS / Home Assistant brand logo
```

---

## 3. Subsystem Breakdown

### 3.1 Cloud REST API Client (`core/api.py`)
- **Transport**: Reuses Home Assistant's managed `aiohttp.ClientSession` via `async_get_clientsession(hass)`.
- **HMAC-SHA1 Signature**: Parameters are sorted alphabetically by key (excluding `sign`), concatenated with `&`, signed with `appSecret`, and formatted as lowercase Base64.
- **Authentication**: Supports password authentication (with client-side lowercase hex SHA256 hashing) and 6-digit email OTP.
- **Payload Normalization**: Unpacks device rosters, SIP credentials, RTSP video URLs, and relays unlock commands (`unlockV2`).

### 3.2 MQTT Push Listener (`core/mqtt.py`)
- **Transport**: Persistent TLS connection to `eu.emqx.gvs-icloud.com:18883`.
- **Subscribed Topics**:
  - `smarthome/device/status` (Broadcast system state events)
  - `smarthome/device/{deviceId}` (Per-device doorbell ring and lock feedback events)
  - `smarthome/device/{homeId}` (Plant-level device state transitions)
  - `smarthome/device/status/{homeId}` (Plant-level broadcast events)
- **Event Correlator**: Maps raw payload actions (`monitoring` action `1` = ring, `0` = idle) to integration call state transitions.

### 3.3 GVS Protocol Engine (`core/protocol.py`)
- **Transport**: Local UDP datagrams on port `8300`.
- **Frame Layout**: 10-byte magic header `47 56 53 47 56 53 A5 A5 A5 A5` (`b"GVSGVS\xa5\xa5\xa5\xa5"`), uint16_be payload length, function ID, command ID, source device type & 6-byte room address, destination device type & 6-byte room address, command payload, and CRC16 checksum.
- **Function Codes**:
  - `TALKBACK_FUNCTION = 3`: Call initiation, answering, and status queries.
  - `ENTRANCEGUARD_FUNCTION = 4`: Lock control and access events.

### 3.4 Cloud SIP + SRTP Video Engine & Local Audio Bridge (`core/cloud_sip.py` & `core/sip_session.py`)
- **2-Wire TS-SMART Architectural Discovery (`protocol="0"`)**:
  - 2-wire indoor monitors (`VI2F-PIT7WF`, `TS-SMART7xx`, `TS-SMART10xx`) do not support RTSPS on port 8322. Live video streaming requires a direct Cloud SIP session.
  - **Cloud SIP Signaling**: Operates on `eu.open-sips.gvs-icloud.com:5060` using standard SIP digest authentication combined with 14 proprietary GVS/AVE headers:
    - Mandatory headers include `enableVideo: 1`, `proxyDeviceId`, `proxyFlag: 1`, `tenantUuid`, `appUuid`, `version`, `clientType`, and `targetCallId`.
  - **SRTP Media Encryption**: Mandates secure RTP profile `RTP/SAVP` with cryptographic suite `AES_CM_128_HMAC_SHA1_80` negotiated via SDP `a=crypto:1 ...`.
  - **Symmetric RTP NAT Hole-Punching**: Home Assistant transmits an initial probe packet from its local UDP port to the remote media server address/port negotiated in the `200 OK` SDP. This opens bi-directional pinholes in stateful NAT routers and firewalls, allowing incoming SRTP H.264 packets to flow in.
  - **H.264 Depacketization & Transcoding**: Decrypts inbound SRTP packets, depacketizes RFC 6184 H.264 NAL units (supporting Single NAL, STAP-A, and FU-A fragmentation units), formats into Annex-B bitstream (`0x00000001` start codes), and pipes into FFmpeg (`image2pipe`) generating continuous low-latency JPEG frames.
- **Local SIP Session & RTP PCMA Audio Bridge (`core/sip_session.py`)**:
  - SIP 2.0 over UDP/TCP port `5060` for local LAN intercom units.
  - Ingests RTP PCMA (G.711a, 8kHz, 8-bit A-law) on UDP `8302`, decodes to PCM16, and relays bi-directionally to the WebSocket API.

### 3.5 WebSocket Audio Bridge (`websocket_api.py`)
- **`ave_video44/call_control`**: Commands for `answer`, `hangup`, `reject`, `unlock`, and `mute`.
- **`ave_video44/audio_subscribe`**: Real-time downstream audio stream delivered to the Lovelace card.
- **`ave_video44/audio_tx`**: Real-time upstream microphone audio sent from the Lovelace card.

### 3.6 Data Coordinator (`coordinator.py`)
- Coordinates device state between polling updates, real-time MQTT events, and local UDP packet reception.
- Manages optimistic state transitions and dispatches event triggers for Home Assistant automations.

### 3.7 Entity Platforms
- **`camera.py`**: Delivers instant MJPEG streaming (`multipart/x-mixed-replace; boundary=--frameboundary`) and still frames (`async_camera_image`) sourced from the active Cloud SIP/SRTP session (`CloudSipMediaSession`) or RTSP stream, with `async_wait_for_wake` frontend-backend coordination preventing HTTP 502 race conditions. On 2-wire installations, returns `None` and disables `CameraEntityFeature.STREAM` when idle, activating dynamically only during calls or active monitoring.
- **`lock.py`**: Dual-lock control (`Lock 1` pedestrian, `Lock 2` driveway) with automated relock after `unlock_pulse_duration` (default: 2s).
- **`button.py`**:
  - `button.*_attiva_telecamera` (`AveVideo44WakeCameraButton`): Enabled by default. Wakes 2-wire outdoor stations on demand via `POST /smarthome/api/device-monitoring/monitoring` (`action=1`), dynamically provisioning the RTSP stream URL and transitioning state to `monitoring`.
  - Instant trigger buttons for pedestrian and driveway unlocking: Configured with `_attr_entity_registry_enabled_default = False` to prevent visual clutter in Home Assistant dashboards alongside primary `lock` entities, while remaining available in the Entity Registry for users requiring pulse shortcuts or automations.
- **`event.py`**: Doorbell call events (`doorbell_press`, `call_answered`, `call_missed`) using `EventDeviceClass.DOORBELL`.
- **`binary_sensor.py`**: Active call state and network connectivity binary sensors.
- **`sensor.py`**: Current call lifecycle state (`idle`, `ringing`, `talking`, `monitoring`) and call duration telemetry.
- **`select.py`**: Dynamic intercom extension selector configured via the integration's address book (`HOUSETOHOUSE`), filtering out the monitor's own SIP URI and defaulting to `Nessun interfono configurato` when empty.
- **`diagnostics.py`**: Anonymized diagnostics export with redaction of tokens, passwords, and sensitive keys.

### 3.8 Frontend Subsystem & Card Auto-Registration (`frontend/`)
- **Bubble Card Redesign**: Implements modern Bubble Card interface conventions (`border-radius: 28px` pill card container, `border-radius: 50%` circular icon bubbles inside full-pill action buttons, floating status badge, rounded 16:9 video frame).
- **Customizable Title & Visual Editor**: Card title is fully customizable via `config.title` / `Titolo Card` in `AveVideo44CardEditor` (defaulting to `"AVE Video V44"`).
- **Responsive Layout**: Desktop auto-fit grid and mobile view constrained to `max-width: 780px` in panel view.
- **Zero-YAML Injection & Anti-Cache Endpoint**: `card_loader.py` serves the card at `/ave_video44_card/ave-video44-card.js?v={VERSION}` with `cache_headers=False` (with backwards-compatible alias at `/ave_video44_frontend/`) and programmatically inserts it as a JavaScript module into Home Assistant's Lovelace resource storage (`lovelace.resources`) and `add_extra_js_url`. This bypasses aggressive mobile WebView / Service Worker caching.
- **Entity Auto-Discovery**: Implements `getStubConfig(hass, entities, [entity])` and `_autoResolveEntities` to automatically scan the Home Assistant entity registry for AVE cameras, locks, doorbell sensors, and address book selectors, populating card fields instantly when added via the visual card picker.
- **On-Demand Camera Wake Control**: The Lovelace card includes an idle `"Attiva Video"` (`#btnMonitor`) button that wakes 2-wire cameras via WebSocket action `monitor`.

### 3.9 Guided Intercom Configuration Flow (`config_flow.py`)
- **Guided OptionsFlow Wizard**: Multi-step interactive flow with dedicated sub-dialogs:
  - `init`: Menu presenting options for 1-click Auto-Discovery, Add or Edit Contact, Remove Contact, or General Settings.
  - `auto_discover`: 1-click discovery scanning `user-current-home`, `monitoring-list`, and local UDP 8300 broadcasts to automatically detect and import room monitors, indoor extensions (`deviceIntercomInfo`), and doorstations (`extraConfig`).
  - `add_contact`: Structured form with inputs for Contact Name (Room/Label) and Intercom Extension Code / Address (e.g., `0102`, `1-1-102` or IP/SIP). Validates against duplicates and formats into canonical options storage.
  - `remove_contact`: Dropdown picker to select and delete an obsolete contact in a single click.
  - `general_settings`: Configures relay pulse duration, preferred RTSP video stream profile, and sidebar dashboard panel visibility (`enable_sidebar_panel`).
- **Automatic Startup Seeding**: When the integration initializes with an empty `intercom_book`, the coordinator automatically seeds extension mappings from device metadata.

---

## 4. Multi-Account and Multi-Monitor Topology

The integration supports complex hardware deployments across residential and commercial buildings:

### 4.1 Single-Account Master/Slave Deployments
- Multiple indoor monitors (e.g., Master `TS-SMART7xx` and Slave monitors) sharing a single cloud `homeId` are discovered under a single `ConfigEntry`.
- Each physical monitor is registered as a distinct device in Home Assistant with individual call state and telemetry sensors.

### 4.2 Multi-Account Distributed Installations
- Separate apartments or floors configured under independent AVE cloud accounts can each be added as a distinct `ConfigEntry`.
- Inter-apartment calls route locally over LAN using the `HOUSETOHOUSE` protocol (`1-1-101`, `1-1-102`), bypassing cloud servers completely.
- A unified address book shared across entries enables seamless calling between monitors on different accounts.

---

## 5. Security & Privacy

1. **Zero Plaintext Secrets**: Passwords, session tokens, HMAC keys, and API secrets are never stored in plaintext or logged.
2. **Encrypted Storage**: Credentials are encrypted within Home Assistant's native `ConfigEntry` storage.
3. **Diagnostics Sanitization**: `diagnostics.py` automatically scrubs all authorization tokens, session IDs, passwords, and IP addresses before generating diagnostic exports.
4. **Local LAN Priority**: Where local network connectivity is available, media streams (RTSP/SIP) can be routed directly within the local subnet, ensuring video and audio remain strictly on the private network.
