# AVE Video V44 — Low-Level Implementation & Algorithmic Details

> **Component Scope**: `custom_components/ave_video44` & Async Core Client  
> **Platform**: AVE Video V44 / GVS Intercom Systems (V44 EASY, V44 SMART)

---

## 1. Networking & Session Management

### 1.1 Mandatory Session Reuse
- Under no circumstances should individual classes or helper methods instantiate unmanaged `aiohttp.ClientSession()` objects directly.
- In Home Assistant runtime, obtain the session exclusively from `homeassistant.helpers.aiohttp_client.async_get_clientsession(hass)`.
- When running outside Home Assistant (e.g. standalone test harnesses or CLI utilities), accept an injected `aiohttp.ClientSession` in the client constructor:

```python
class AveVideo44ApiClient:
    def __init__(self, session: aiohttp.ClientSession, base_url: str = DEFAULT_BASE_URL) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._session_id: str | None = None
        self._auth_lock = asyncio.Lock()
```

### 1.2 Non-Blocking Timeouts
- All network operations must pass explicit timeouts (`asyncio.timeout(10.0)` or `aiohttp.ClientTimeout(total=15.0)`).
- Never allow an unbounded network request or hanging socket to freeze the event loop or block the coordinator cycle.

---

## 2. Cloud REST API & Cryptographic Signing

### 2.1 HMAC-SHA1 Request Signing (`compute_gvs_sign`)
The AVE/GVS cloud REST endpoints require an HMAC-SHA1 signature over all query and body parameters. Disassembly of `com.gvs.smart.ave` (APK v2.1.2, `StringUtil.toEncryption`) reveals a verified double-Base64 encoding scheme:
1. Filter out the `sign` key and any keys with `None` values.
2. Sort remaining parameter keys in ascending alphabetical order.
3. Format as standard key-value pairs concatenated with `&`: `k1=v1&k2=v2`.
4. **Base64 Pre-Encoding**: Encode the ASCII query string into a Base64 string before hashing: `query_b64 = base64.b64encode(query_str.encode("utf-8"))`.
5. Compute the HMAC-SHA1 digest using the integration's `appSecret` as the key over `query_b64`: `mac = hmac.new(secret.encode("utf-8"), query_b64, hashlib.sha1).digest()`.
6. Encode the resulting HMAC digest in Base64 and convert the string to lowercase:

```python
def compute_gvs_sign(params: dict[str, Any], secret: str = DEFAULT_APP_SECRET) -> str:
    """Verified double-Base64 HMAC-SHA1 signing matching APK v2.1.2."""
    sorted_pairs = [
        f"{k}={params[k]}"
        for k in sorted(params.keys())
        if k != "sign" and params[k] is not None
    ]
    query_str = "&".join(sorted_pairs)
    query_b64 = base64.b64encode(query_str.encode("utf-8"))
    mac = hmac.new(secret.encode("utf-8"), query_b64, hashlib.sha1).digest()
    return base64.b64encode(mac).decode("utf-8").lower()
```

Formula: `base64(HMAC-SHA1(secret, base64(sorted_query_string))).lower()`

### 2.2 APK v2.1.2 Retrofit Endpoint Contract & Envelope Parsing
In official Android APK v2.1.2, network calls are defined via Retrofit interfaces exhibiting specific query vs body mappings:
- **`POST /usercenter/api/uc/loginToGvs/email`**:
  - `@QueryMap`: Common query parameters (`tenantUuid`, `appUuid`, `ts`, `sign`) must be passed in the URL query string.
  - `@FieldMap`: Form-urlencoded payload (`account`, `password`, `channel="App"`, or `email`, `code`) is transmitted in the HTTP POST body with `Content-Type: application/x-www-form-urlencoded`.
- **Response Envelope Structure (`"result"` vs `"data"`)**:
  - Cloud responses wrap their payload inside either `"result"` or `"data"` (e.g. `{"code": 200, "msg": "success", "result": {...}}`).
  - Parsing must dynamically evaluate `resp_json.get("result") or resp_json.get("data") or {}` to accommodate both endpoint variations.
- **Session Cookie (`JSESSIONID`)**:
  - The server issues a `Set-Cookie: JSESSIONID=...` header on initial authentication.
  - The cookie must be captured and transmitted in subsequent HTTP requests alongside `token` and `sessionId` headers.
- **Plant & Device Endpoints**:
  - `GET /smarthome/api/home/queryHomeList`: Returns registered smart home installations.
  - `GET /smarthome/api/quick-display-device/user-current-home`: Returns configured quick display intercom stations for the current plant.
  - `GET /smarthome/api/device/getInfo`: Retrieves comprehensive device metadata and hardware status.

### 2.3 Password Hashing
- User account passwords are encrypted client-side before transmission: `hashlib.sha256(password.encode("utf-8")).hexdigest().lower()`.
- The plaintext password is never retained in memory after the authentication exchange or stored on disk.

### 2.4 Transient Failure Resilience
- On HTTP 429 (Too Many Requests) or 5xx server responses, the client applies truncated exponential backoff with jitter:
  $$T_{\text{wait}} = \min(T_{\max}, 2^{\text{attempt}} \cdot \text{base}) \cdot \text{random}(0.5, 1.5)$$
- Standard parameters: `base = 1.0`s, `T_max = 30.0`s, `max_retries = 3`.

---

## 3. Binary Framing Protocol (`protocol.py`)

### 3.1 UDP Framing Structure (Port 8300)
The local GVS control protocol operates over UDP port 8300 with binary framing:

```
Offset    Size      Type         Description
0         10        bytes        Magic Header: 47 56 53 47 56 53 a5 a5 a5 a5 (b"GVSGVS\xa5\xa5\xa5\xa5")
10        2         uint16_be    Payload byte length (N)
12        1         uint8        Function ID (e.g., 4 for ENTRANCEGUARD, 3 for TALKBACK)
13        1         uint8        Command ID (e.g., 11 for COM_REMOTE_UNLOCK_ASK)
14        1         uint8        Source Device Type (e.g., 97 for DEV_INDOORPHONE)
15        6         bytes        Source Room Address (6 bytes: building, stair, floor, room, sub, res)
21        1         uint8        Destination Device Type (e.g., 50 for DEV_DOORSTATION)
22        6         bytes        Destination Room Address (6 bytes)
28        N-16      bytes        Command-specific payload
12+N      2         uint16_be    CRC16 / Checksum (0x0000 if unused)
```

### 3.2 Room Address Encoding
- Room addresses are structured as a 6-byte array: `[building, staircase, floor, room, sub_unit, reserved]`.
- For string representations such as `1-1-101`, the components map to building 1, staircase 1, and room number 101.

---

## 4. Real-Time Audio Resampling & Bridge Pipeline

```
[Browser Mic] ──(44.1/48kHz)──► [WebAudio ScriptProcessor / Worklet]
                                             │ (8kHz mono PCM16)
                                             ▼
                                    [WebSocket: ave_video44/audio_tx]
                                             │
                                             ▼
                                    [HA websocket_api.py]
                                             │ (transcode to G.711a A-law)
                                             ▼
                                    [RTP Packetizer (PT=8)]
                                             │ (UDP 8302)
                                             ▼
                                   [AVE Intercom DSP]
```

### 4.1 Downstream Audio (Intercom to Browser)
1. The outdoor station transmits RTP audio packets on UDP port `8302` containing PCMA (G.711a, 8000 Hz, 8-bit A-law) frames.
2. `core/sip_session.py` decodes A-law bytes into signed 16-bit mono PCM little-endian samples.
3. `websocket_api.py` dispatches binary WebSocket frames to subscribed Lovelace clients (`ave_video44/audio_subscribe`).
4. `ave-video44-card.js` writes the PCM16 audio buffers to an HTML5 `AudioContext` for playback.

### 4.2 Upstream Audio (Browser to Intercom)
1. Browser captures microphone stream via `navigator.mediaDevices.getUserMedia`.
2. Lovelace card resamples raw browser audio (typically 44.1kHz or 48kHz) down to 8000 Hz 16-bit mono PCM.
3. Card sends 20ms chunks (160 samples = 320 bytes) via WebSocket binary message (`ave_video44/audio_tx`).
4. `websocket_api.py` converts PCM16 samples to G.711a A-law.
5. Audio is packetized into standard RTP packets (Payload Type 8, 20ms timestamp step of 160) and sent via UDP socket to the doorstation audio port.

### 4.3 Android WebView Legacy Syntax Compatibility
- The bundled Lovelace card (`ave-video44-card.js`) must strictly avoid modern ECMAScript operators:
  - **No Optional Chaining**: Replace `a?.b` with `(a && a.b)`.
  - **No Nullish Coalescing**: Replace `a ?? b` with `(a !== null && a !== undefined ? a : b)`.
- Wall-mounted Android displays (Android 8–10) running legacy WebViews fail to parse scripts containing these operators, causing the element to crash silently.

---

## 5. Lock Actuation & Auto-Relock Lifecycle

```
[User Action] ──► LockEntity.async_unlock()
                         │
                         ├──► 1. Set state to unlocking
                         ├──► 2. Dispatch unlock request (cloud REST unlockV2 or local SIP INFO / UDP)
                         ├──► 3. Set state to unlocked
                         │
                         └──► 4. Launch asyncio.sleep(unlock_pulse_duration) [default: 2s]
                                      │
                                      ▼
                              5. Reset state to locked
```

- **Dual-Lock Addressing**:
  - `Lock ID 1`: Pedestrian pedestrian gate.
  - `Lock ID 2`: Driveway vehicular sliding gate.
- **Relock Guard**: The timer runs in a non-blocking asynchronous task; subsequent unlock requests reset the pulse timer without blocking coordinator execution.

---

## 6. Diagnostics & Sensitive Data Redaction

All diagnostic dumps produced by `diagnostics.py` must redact:
- **Authentication Tokens**: `sessionId`, `token`, `appSecret`, `sign`, `authorization`.
- **Credentials**: `password`, OTP codes, SIP passwords.
- **Network Identifiers**: Cloud session cookies, external IP addresses, MAC addresses.

```python
TO_REDACT = {
    "password",
    "sessionId",
    "token",
    "appSecret",
    "sign",
    "authorization",
    "cookie",
}
```

---

## 7. Home Assistant Entity Conventions

### 7.1 Unique ID Determinism
- Unique IDs for entities must follow the format:
  `{entry.entry_id}_{device_id}_{entity_key}`
- Example: `01J9K..._doorstation_001_pedestrian_lock`

### 7.2 Device Association
- All entities created for an outdoor station or indoor monitor must provide `device_info`:
```python
@property
def device_info(self) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, self._device_id)},
        name=self._device_name,
        manufacturer="AVE / GVS",
        model=self._device_model or "AVE Video V44",
        sw_version=self._firmware_version,
    )
```

---

## 8. Home Assistant 2025/2026 OptionsFlow Contract & Self-Healing

### 8.1 Read-Only `OptionsFlow.config_entry` Property Invariant
In Home Assistant Core 2024.11, 2025.x, and 2026.x, `config_entries.OptionsFlow.config_entry` is declared as a read-only `@property`:

```python
@property
def config_entry(self) -> ConfigEntry:
    return self._config_entry
```

- **Invariant**: Subclasses must NEVER execute `self.config_entry = config_entry` in `__init__`. Doing so triggers an unhandled `AttributeError: property 'config_entry' of 'AveVideo44OptionsFlow' object has no setter`, crashing the Options ("Configure") dialog.
- **Pattern**:
  ```python
  class AveVideo44OptionsFlow(config_entries.OptionsFlow):
      """Handle options for AVE Video V44."""

      # In HA 2024+, async_get_options_flow automatically handles entry association.
      # Access self.config_entry directly through the base property without manual assignment.
  ```

### 8.2 Coordinator State Self-Healing
In `AveVideo44Coordinator`, when initializing or updating state:
- If a pre-existing config entry lacks `homeId` or possesses an expired session cookie, the coordinator executes an automatic self-healing routine:
  1. Refreshes cloud authentication tokens and reacquires `JSESSIONID`.
  2. Queries `GET /smarthome/api/home/queryHomeList` to resolve the active `homeId`.
  3. Updates the entry's runtime state dynamically without breaking entity bindings or demanding manual integration reconfiguration.

---

## 9. Frontend Lovelace Card Auto-Registration & Visual Editor Contract

### 9.1 Zero-YAML Resource Registration & Cache-Bypass (`/ave_video44_card/`)
The custom element card is automatically registered during integration setup without requiring manual dashboard resource entry:

```python
async def async_register_card(hass: HomeAssistant) -> None:
    """Register custom Lovelace card via static path and Lovelace resources."""
    from homeassistant.components.frontend import add_extra_js_url

    card_path = Path(__file__).parent / "ave-video44-card.js"
    url_path = f"/ave_video44_card/ave-video44-card.js?v={VERSION}"
    
    # Register static path with cache_headers=False to bypass immutable WebView caching
    hass.http.register_static_path(
        "/ave_video44_card/ave-video44-card.js",
        str(card_path),
        cache_headers=False,
    )
    # Maintain legacy alias for backward compatibility
    hass.http.register_static_path(
        "/ave_video44_frontend/ave-video44-card.js",
        str(card_path),
        cache_headers=False,
    )
    add_extra_js_url(hass, url_path)

    # Programmatic registration in Lovelace Storage Resources
    resources = getattr(hass.data.get("lovelace"), "resources", None)
    if resources and hasattr(resources, "async_create_item"):
        # Ensures card is declared as res_type: "module" in .storage/lovelace_resources
        ...
```

- **Cache-Busting & Path Switch**: Serving the card on `/ave_video44_card/ave-video44-card.js?v={VERSION}` with `cache_headers=False` bypasses immutable 31-day Service Worker and mobile Companion App WebView caches.
- **Fail-Safe Loading**: The loader handles headless and unit test environments gracefully where `hass.http` or `frontend` may not be initialized.

### 9.2 Custom Card Visual Editor (`ave-video44-card-editor`) & Bubble Card Architecture
To support Home Assistant's UI card picker, modern dashboard visual standards, and panel responsiveness:
- **Card Registration**:
  ```javascript
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "ave-video44-card",
    name: "AVE Video V44 Card",
    description: "Control AVE Video V44 intercoms with live video, audio, and door unlock.",
    preview: true,
  });
  ```
- **Bubble Card Styling & DOM Layout**:
  - Container: Pill container (`border-radius: 28px`) with subtle dark blur backdrop.
  - Buttons: Full-pill action buttons (`.bubble-pill-btn`, `border-radius: 999px`) containing a circular icon bubble (`.bubble-icon`, `border-radius: 50%`) and text label.
  - Viewport: Rounded 16:9 video frame (`border-radius: 22px`). Element `<video id="liveVideo">` remains hidden while empty, with automatic fallback and retry on `cameraStreamImg` during 2-wire wake-up transitions.
  - Responsive Grid: `repeat(auto-fit, minmax(200px, 1fr))` on desktop, responsive adaptive layout on mobile, constrained to `max-width: 780px` in panel view.
- **Customizable Title**: Card title is configurable via YAML (`title: ...`) or in the visual card editor (`Titolo Card`, defaulting to `"AVE Video V44"`).
- **Editor Element Hook**: `AveVideo44Card.getConfigElement()` returns a newly instantiated `document.createElement("ave-video44-card-editor")`.
- **Dynamic Entity Auto-Discovery (`getStubConfig`)**:
  ```javascript
  static getStubConfig(hass, entities, [entity]) {
    const states = hass && hass.states ? Object.keys(hass.states) : [];
    const findEntity = (prefix, fallback) => {
      const match = states.find(id => id.startsWith(prefix) && (id.includes("posto_esterno") || id.includes("ave_video44")));
      return match || fallback || "";
    };
    return {
      type: "custom:ave-video44-card",
      title: "AVE Video V44",
      entity: findEntity("camera.", "camera.posto_esterno_ingresso"),
      intercom_select: findEntity("select.", "select.rubrica_interni"),
      call_state_sensor: findEntity("sensor.", "sensor.posto_esterno_stato_chiamata"),
      doorbell_binary_sensor: findEntity("binary_sensor.", "binary_sensor.posto_esterno_chiamata_in_corso"),
      lock_pedestrian: findEntity("lock.", "lock.posto_esterno_cancelletto_pedonale"),
      lock_driveway: findEntity("lock.", "lock.posto_esterno_cancello_carraio"),
    };
  }
  ```
- **Visual Editor Lifecycle**: `AveVideo44CardEditor` observes configuration changes via property setters, populates dropdown pickers (`ha-entity-picker`) filtered by entity domain, and fires standard `config-changed` custom events with updated configuration dictionaries.

---

## 10. Entity Registry Disabled-by-Default Policy & Relay Coexistence

### 10.1 Lock vs Button Entity Coexistence
The integration provides two mechanisms to operate doorstation relays:
1. **Primary Control — `lock` entities** (`lock.posto_esterno_cancelletto_pedonale`, `lock.posto_esterno_cancello_carraio`):
   - Fully represent lock state (`locked`, `unlocking`, `unlocked`).
   - Feature automated relock timers with configurable pulse duration.
   - Integrate seamlessly with Home Assistant security dashboards and voice assistants.
2. **Instant Pulse — `button` entities** (`button.apri_cancelletto`, `button.apri_cancello_carraio`):
   - Configured with `_attr_entity_registry_enabled_default = False`.
   - Prevent UI clutter and duplicate switches in automatically generated Home Assistant dashboard views.
   - Remain available in the Entity Registry for users wishing to bind instant pulse actions to physical wall buttons, shortcuts, or automations.

### 10.2 Non-Destructive Registry Upgrades
Setting `_attr_entity_registry_enabled_default = False` at the entity class level only affects newly created or discovered entities. Users who previously enabled or explicitly disabled button entities in their entity registry retain their customized visibility settings without breaking automations.

---

## 11. On-Demand Camera Wake & Monitoring Session Lifecycle

### 11.1 2-Wire Doorstation Energy Optimization & Wake Endpoint
In 2-wire installations (`TS-SMART` indoor monitor + 2-wire doorstation), the outdoor unit camera is physically powered down when idle to conserve energy and bus power. Attempting to connect to the idle RTSP stream yields `Connection refused`.

To wake the outdoor station camera on demand, the integration calls `POST /smarthome/api/device-monitoring/monitoring`:
```json
{
  "action": 1,
  "deviceId": "<indoor_monitor_deviceId>",
  "monitoringDeviceNumber": "1",
  "resolutionLevel": 0
}
```
- **Response**: Returns `statusCode: 200` and `result: "<callId>"` representing the active monitoring session transaction ID.
- **RTSPS Stream Construction**: When the monitor activates, the coordinator builds the cloud RTSPS URL:
  `rtsps://{user}:{pwd}@{domain}:8322/stream/1/{deviceId}/0/{targetNum}`
  using `rtsp_cfg["auth"]["basic"]["username"]`, `rtsp_cfg["auth"]["basic"]["password"]`, and `ports.rtsps` (`8322`).
- **Dynamic MQTT Synchronization**: On incoming MQTT event `"code": "monitoring"` with `value.result.serverUrl`, the coordinator dynamically refreshes `active_rtsp_url`.
- **FFmpeg MJPEG Camera Proxy**: In `camera.py`, `async_camera_image` and `handle_async_mjpeg_stream` return `None` when idle (preventing FFmpeg connection loops when unpowered) and spawn FFmpeg with `-rtsp_transport tcp` when `active_rtsp_url` is active.

### 11.2 Graceful Monitoring Session Teardown (`action: 3`)
- When the user stops previewing or the call ends, the coordinator invokes `POST /smarthome/api/device-monitoring/monitoring` with `action: 3`.
- **API Invariant**: The cloud API requires `action: 3` for session termination; sending `action: 0` is rejected with error `-1000000400`.
- The coordinator clears `active_rtsp_url = None` and resets `call_state = "idle"`.

---

## 12. Intercom Auto-Discovery & Startup Seeding

### 12.1 Auto-Discovery Engine (`async_discover_intercoms`)
- Queries `GET /smarthome/api/quick-display-device/user-current-home` and `GET /smarthome/api/device-monitoring/monitoring-list`.
- Extracts:
  - Outdoor station relays from `extraConfig`: `{"deviceNumber": "1", "deviceName": "Citofono"}`.
  - Indoor extensions from `deviceIntercomInfo`: `haZone`, `username`, room addresses.
  - Discovered local endpoints via UDP 8300 `COM_PING_ASK` broadcast.

### 12.2 Startup Seeding & Guided OptionsFlow
- **Auto-Seeding**: During integration setup, if `intercom_book` is empty in options, the coordinator invokes `async_discover_intercoms()` and auto-populates the dictionary into `entry.options`.
- **OptionsFlow Integration**: Exposes `auto_discover` as the top-level option in `AveVideo44OptionsFlow`. Clicking it triggers discovery and persists newly found contacts in a single step without manual text editing.

---

## 13. Sidebar Dashboard Panel Management (`enable_sidebar_panel`)

The integration offers an optional dedicated sidebar panel dashboard (`Videocitofono`) served in full panel mode (`"type": "panel"`):
- **Configuration Option**: Managed via `CONF_ENABLE_SIDEBAR_PANEL` (`enable_sidebar_panel`, default `True`) in OptionsFlow settings.
- **Dynamic Synchronization**: Handled in `__init__.py` via `_async_sync_sidebar_panel(hass, entry)`, creating or updating the panel registration in `.storage/lovelace_dashboards` and matching `show_in_sidebar`.
- **Zero-YAML Layout**: The generated sidebar dashboard embeds `custom:ave-video44-card` configured with auto-resolved entities and constrained responsive width.

---

## 14. Cloud SIP + SRTP Video Engine (`CloudSipMediaSession`)

### 14.1 2-Wire Hardware Video Protocol Discovery (`protocol="0"`)
For 2-wire cloud installations (`TS-SMART` indoor monitors including `VI2F-PIT7WF`, `TS-SMART7xx`, and `TS-SMART10xx`), the cloud REST API reports `protocol="0"`. These units do not expose or proxy an RTSPS video stream on port 8322. Live video transmission requires initiating an authenticated SIP session directly with the AVE/GVS cloud SIP proxy:
- **SIP Proxy Endpoint**: `eu.open-sips.gvs-icloud.com:5060` (UDP).
- **Authentication**: Standard SIP digest challenge-response (`401 Unauthorized` / `407 Proxy Authentication Required`, MD5 hashing).

### 14.2 Proprietary GVS/AVE 14 Custom SIP Headers
To route the call to the unpowered 2-wire doorstation through the cloud registrar and wake the camera feed, the SIP `INVITE` must contain 14 proprietary headers:
```
enableVideo: 1
proxyDeviceId: <indoor_monitor_deviceId>
proxyFlag: 1
tenantUuid: <tenantUuid>
appUuid: <appUuid>
version: 2.1.2
clientType: 1
targetCallId: <monitoring_or_ring_call_id>
```
- **Crucial Invariant**: Omission of `enableVideo: 1` causes the server to negotiate audio-only or immediately drop the dialog with `488 Not Acceptable Here`.

### 14.3 Mandatory SRTP Media Encryption (`RTP/SAVP`)
The media exchange mandates SRTP encryption for all video transport:
- **SDP Crypto Offer**: `a=crypto:1 AES_CM_128_HMAC_SHA1_80 inline:<master_key_salt_30_bytes_base64>`
- The media transport profile in SDP is declared strictly as `RTP/SAVP` with payload type `96` (`H264/90000`).
- SRTP packets are decrypted via cryptographic contexts established with `pylibsrtp` and `cryptography`.

### 14.4 Symmetric RTP NAT Hole-Punching
Because Home Assistant typically resides behind home router NATs:
1. `CloudSipMediaSession` binds a local ephemeral UDP port for video RTP.
2. Upon receiving `200 OK` with remote media server IP and port, it immediately transmits an initial dummy probe packet from that local port to the remote media port.
3. This creates a stateful NAT translation mapping in consumer routers, enabling the remote media server to deliver encrypted SRTP packets into Home Assistant without requiring manual port forwarding on the router.

### 14.5 H.264 Annex-B Depacketization & FFmpeg MJPEG Pipe
1. Inbound SRTP packets are decrypted and stripped of the 12-byte RTP header.
2. Payload is parsed for RFC 6184 H.264 packet types:
   - **Single NAL Unit**: Prefix with 4-byte Annex-B start code `0x00000001`.
   - **STAP-A (Type 24)**: Unpack aggregated NAL units and prefix each with `0x00000001`.
   - **FU-A (Type 28)**: Reconstruct fragmented NAL units across multiple RTP packets, prepending `0x00000001` upon encountering the start bit.
3. The Annex-B elementary stream is piped to a long-running asynchronous FFmpeg worker:
   ```bash
   ffmpeg -f h264 -i pipe:0 -f image2pipe -vcodec mjpeg -q:v 3 pipe:1
   ```
4. Decoded JPEG frames are stored in an asynchronous memory buffer, providing zero-latency delivery to `AveVideo44Camera.async_camera_image` and `handle_async_mjpeg_stream`.


