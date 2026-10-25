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

