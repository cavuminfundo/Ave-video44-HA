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
│  │  │ - mqtt.py: TLS MQTTS Push Listener (:8883)                 │  │  │
│  │  │ - protocol.py: GVS UDP 8300 Binary Framing Engine          │  │  │
│  │  │ - sip_session.py: SIP Signaling & RTP PCMA Audio Bridge    │  │  │
│  │  └──────────────────────────────┬─────────────────────────────┘  │  │
│  │                                 │                                │  │
│  │  ┌──────────────────────────────┴─────────────────────────────┐  │  │
│  │  │ Entities: camera, lock, button, event, binary_sensor,      │  │  │
│  │  │           sensor, select, diagnostics                      │  │  │
│  │  └────────────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────┬──────────────────────────────┬────────┘  │
│                             │                              │           │
│                             │ WebSocket PCM16              │           │
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
       HTTPS / MQTTS :8883    │                              │ UDP 8300 / SIP :5060 / RTSP :554
       (Cloud Push & REST)    │                              │ (Local LAN Control & Media)
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
├── camera.py                  ← RTSP H.264 camera entity with snapshot preview
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
│   ├── mqtt.py                ← Async MQTTS client listening on eu.emqx.gvs-icloud.com:8883
│   ├── protocol.py            ← GVS binary protocol framing (magic header GVSGVS\xa5\xa5\xa5\xa5)
│   └── sip_session.py         ← SIP 2.0 user agent & RTP PCMA / PCM16 audio bridge
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
- **Transport**: Persistent TLS connection to `eu.emqx.gvs-icloud.com:8883`.
- **Subscribed Topics**:
  - `smarthome/device/status` (Broadcast system state events)
  - `smarthome/device/{deviceId}` (Per-device doorbell ring and lock feedback events)
- **Event Correlator**: Maps raw payload actions (`monitoring` action `1` = ring, `0` = idle) to integration call state transitions.

### 3.3 GVS Protocol Engine (`core/protocol.py`)
- **Transport**: Local UDP datagrams on port `8300`.
- **Frame Layout**: 10-byte magic header `47 56 53 47 56 53 A5 A5 A5 A5` (`b"GVSGVS\xa5\xa5\xa5\xa5"`), uint16_be payload length, function ID, command ID, source device type & 6-byte room address, destination device type & 6-byte room address, command payload, and CRC16 checksum.
- **Function Codes**:
  - `TALKBACK_FUNCTION = 3`: Call initiation, answering, and status queries.
  - `ENTRANCEGUARD_FUNCTION = 4`: Lock control and access events.

### 3.4 SIP Session & Audio Bridge (`core/sip_session.py`)
- **Signaling**: SIP 2.0 over UDP/TCP port `5060`. Supports remote unlock via SIP `INFO` with `application/gvs_protocol+json` or DTMF.
- **RTP Audio Bridge**:
  - Downstream: Ingests RTP PCMA (G.711a, 8kHz, 8-bit A-law) on UDP `8302`, decodes to 16-bit mono PCM (PCM16 little-endian), and delivers binary frames to the WebSocket API.
  - Upstream: Accepts 8kHz PCM16 binary chunks from WebSocket API, encodes to G.711a A-law, and transmits standard RTP packets (PT 8) to the intercom unit.

### 3.5 WebSocket Audio Bridge (`websocket_api.py`)
- **`ave_video44/call_control`**: Commands for `answer`, `hangup`, `reject`, `unlock`, and `mute`.
- **`ave_video44/audio_subscribe`**: Real-time downstream audio stream delivered to the Lovelace card.
- **`ave_video44/audio_tx`**: Real-time upstream microphone audio sent from the Lovelace card.

### 3.6 Data Coordinator (`coordinator.py`)
- Coordinates device state between polling updates, real-time MQTT events, and local UDP packet reception.
- Manages optimistic state transitions and dispatches event triggers for Home Assistant automations.

### 3.7 Entity Platforms
- **`camera.py`**: Live RTSP stream (`rtsp://open-sips.gvs-icloud.com:554/...` or local LAN RTSP stream) with snapshot preview support.
- **`lock.py`**: Dual-lock control (`Lock 1` pedestrian, `Lock 2` driveway) with automated relock after `unlock_pulse_duration` (default: 2s).
- **`button.py`**: Instant trigger buttons for pedestrian and driveway unlocking. Configured with `_attr_entity_registry_enabled_default = False` to prevent visual clutter in Home Assistant dashboards alongside primary `lock` entities, while remaining available in the Entity Registry for users requiring pulse shortcuts or automations.
- **`event.py`**: Doorbell call events (`doorbell_press`, `call_answered`, `call_missed`) using `EventDeviceClass.DOORBELL`.
- **`binary_sensor.py`**: Active call state and network connectivity binary sensors.
- **`sensor.py`**: Current call lifecycle state (`idle`, `ringing`, `talking`, `monitoring`) and call duration telemetry.
- **`select.py`**: Dynamic intercom extension selector configured via the integration's address book (`HOUSETOHOUSE`). Defaults to `Nessun interfono configurato` when no intercom contacts are registered.
- **`diagnostics.py`**: Anonymized diagnostics export with redaction of tokens, passwords, and sensitive keys.

### 3.8 Frontend Subsystem & Card Auto-Registration (`frontend/`)
- **Zero-YAML Injection**: `card_loader.py` registers the static card asset via `add_extra_js_url(hass, f"/ave_video44_frontend/ave-video44-card.js?v={VERSION}")` upon integration setup. This eliminates manual addition to Lovelace resources and guarantees client cache-busting on version upgrades.
- **Visual Card Editor (`ave-video44-card-editor`)**: The custom element registers `window.customCards` metadata and implements `getConfigElement()` returning an interactive form editor (`AveVideo44CardEditor`).
- **Entity Auto-Discovery**: Implements `getStubConfig(hass, entities, [entity])` and `_autoResolveEntities` to automatically scan the Home Assistant entity registry for AVE cameras, locks, doorbell sensors, and address book selectors, populating card fields instantly when added via the visual card picker.

### 3.9 Guided Intercom Configuration Flow (`config_flow.py`)
- **Guided OptionsFlow Wizard**: Multi-step interactive flow with dedicated sub-dialogs:
  - `init`: Menu presenting options to Add or Edit Contact, Remove Contact, or General Settings.
  - `add_contact`: Structured form with inputs for Contact Name (Room/Label) and Intercom Extension Code / Address (e.g., `0102`, `1-1-102` or IP/SIP). Validates against duplicates and formats into canonical options storage.
  - `remove_contact`: Dropdown picker to select and delete an obsolete contact in a single click.
  - `general_settings`: Configures relay pulse duration and preferred RTSP video stream profile.

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
