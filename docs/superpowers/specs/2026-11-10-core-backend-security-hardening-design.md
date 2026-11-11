# Specifica di Design — Hardening di Sicurezza Backend AVE Video V44 & Gate Pre-Commit Test

**Data**: 2026-11-10  
**Stato**: Approvato dall'utente  
**Ambito**: Backend Core (`websocket_api.py`, `core/sip_session.py`, `__init__.py`, `core/protocol.py`), Regole Workspace (`.agents/AGENTS.md`) e Suite di Test (`tests/`).

---

## 1. Obiettivo
Innalzare la postura di sicurezza dell'integrazione `custom_components/ave_video44` per installazioni domestiche in produzione, eliminando vettori di Credential Leak, Denial of Service (OOM / CPU exhaustion), iniezione/dirottamento UDP (Video FFmpeg e Audio Symmetric RTP), Path Traversal sui descrittori SDP, chiamate non validate ai servizi HA e crash su pacchetti binari GVS troncati. Contestualmente, codificare in `.agents/AGENTS.md` l'obbligo tassativo di eseguire l'intera suite di test prima di qualsiasi `git commit` e `git push`.

---

## 2. Architettura e Modifiche per Modulo (Ponytail Ladder: In-Place Defense)

### 2.1 WebSocket API (`custom_components/ave_video44/websocket_api.py`)
1. **Redazione credenziali RTSP su `action == "monitor"`**:
   - Funzione helper `_redact_rtsp_url(url: Optional[str]) -> Optional[str]` che sostituisce qualsiasi `user:password@` in URL `rtsp://` o `rtsps://` con `***:***@` tramite regex `re.sub(r"(rtsps?://)[^/@]+@", r"\1***:***@", url)`.
   - In `ws_call_control`, `connection.send_result(msg["id"], {"success": True, "rtsp_url": _redact_rtsp_url(rtsp_url)})` evita l'esposizione in chiaro delle credenziali RTSP al browser/frontend.
2. **Validazione lunghezza payload e Rate Limiting in `ws_audio_tx`**:
   - Nello schema Voluptuous di `ws_audio_tx`, limitare `payload` con `vol.All(str, vol.Length(min=1, max=32768))` (32 KB max Base64) e verificare post-decodifica che `len(pcm16_data) <= 24576`.
   - Rate limiting per sessione: in `_AUDIO_TX_SESSIONS[session_key]`, tracciare una finestra mobile di 1 secondo (`window_start`, `window_frames`). Se `window_frames > 150` frame/s, scartare il frame (o sollevare `WebSocketError("rate_limited", ...)` se `ack=True`).
   - Eviction deterministica di `_AUDIO_TX_SESSIONS`: mantenere il tetto rigido `_MAX_AUDIO_TX_SESSIONS = 32`. Dopo aver rimosso le sessioni inattive da `> 30.0s`, se `len(_AUDIO_TX_SESSIONS) >= _MAX_AUDIO_TX_SESSIONS` e la chiave non è presente, rimuovere la voce con `last_active` più vecchio (`min(_AUDIO_TX_SESSIONS, key=lambda k: _AUDIO_TX_SESSIONS[k].get("last_active", 0.0))`).

### 2.2 Sessione SIP & Media (`custom_components/ave_video44/core/sip_session.py`)
1. **Protezione OOM su stream TCP SIP (`_read_sip_msg`)**:
   - Costanti `MAX_SIP_HEADER_BYTES = 16384` (16 KB) e `MAX_SIP_CONTENT_LENGTH = 65536` (64 KB).
   - Nel ciclo di lettura header (`while b"\r\n\r\n" not in self._rx_buf`), se `len(self._rx_buf) > MAX_SIP_HEADER_BYTES`, svuotare il buffer e sollevare `ValueError("SIP header exceeds maximum allowed size")`.
   - Dopo il parsing di `Content-Length`, se `content_len < 0` o `content_len > MAX_SIP_CONTENT_LENGTH`, sollevare `ValueError(f"Invalid or excessive SIP Content-Length: {content_len}")`.
2. **Filtro IP sorgente UDP su socket Video e Audio RTP**:
   - Helper `_is_trusted_udp_source(self, addr: Any) -> bool` su `CloudSipMediaSession`: accetta pacchetti solo se `addr` è una tupla valida il cui IP `addr[0]` appartiene a `{"127.0.0.1", "::1"}` oppure coincide con gli IP remoti autorizzati (`self._remote_ip` o l'host di `self.sip_config.get("server")` / `self.sip_config.get("proxy")`).
   - In `_video_rx_loop`: leggere `pkt, addr = self._video_sock.recvfrom(65535)` e scartare il pacchetto se `not self._is_trusted_udp_source(addr)`.
   - In `_audio_rx_loop`: scartare il pacchetto se `not self._is_trusted_udp_source(addr)`. Nella modalità `RTP/AVP`, aggiornare `self._remote_audio_port = addr[1]` solo se `addr[0] == self._remote_ip`, impedendo a host terzi sulla LAN di dirottare il flusso audio in uscita (Symmetric RTP Hijacking).
   - In `AveSipSession.datagram_received`: se `self.remote_ip` è configurato (diverso da `""` e `"0.0.0.0"`), accettare pacchetti RTP/SIP solo se `addr[0] in (self.remote_ip, "127.0.0.1")`.
3. **Sanitizzazione `device_id` nel path del file SDP temporaneo**:
   - In `CloudSipMediaSession._start_ffmpeg`, costruire `safe_dev_id = re.sub(r"[^a-zA-Z0-9_-]", "", str(self.device_id)) or "unknown"` prima di formare `/tmp/ave_video44_{safe_dev_id}_{uuid.uuid4().hex[:6]}.sdp`.

### 2.3 Schemi Voluptuous Servizi Dominio (`custom_components/ave_video44/__init__.py`)
- Definire gli schemi di validazione per `unlock`, `call_intercom`, `answer_call` e `hangup_call`:
  - `SERVICE_UNLOCK_SCHEMA`: `device_id` obbligatorio (`vol.Any(int, str)`), `lock_id` opzionale (`vol.All(vol.Coerce(str), vol.In(["1", "2"]))`, default `"1"`), `entry_id` opzionale (`str`).
  - `SERVICE_CALL_INTERCOM_SCHEMA`: `device_id` obbligatorio (`vol.Any(int, str)`), `room_code` opzionale (`vol.All(str, vol.Length(min=1, max=32))`), `entry_id` opzionale (`str`).
  - `SERVICE_CALL_ACTION_SCHEMA`: `device_id` opzionale (`vol.Any(int, str)`), `entry_id` opzionale (`str`).
- Passare lo schema corrispondente a `hass.services.async_register(DOMAIN, name, handler, schema=schema)`.

### 2.4 Bounds Checking Protocollo GVS (`custom_components/ave_video44/core/protocol.py`)
- In `parse_gvs_udp_packet(packet: bytes)`:
  - Verificare che `payload_length >= 16` e `len(packet) >= 28` prima di indicizzare `packet[12..28]`, sollevando `ValueError("Truncated GVS header payload: payload_length must be >= 16")` invece di `IndexError`.

### 2.5 Regola Obbligatoria Pre-Commit/Push in `.agents/AGENTS.md`
- Aggiornare le sezioni `## 5. Mandatory Release, Versioning & Changelog Policy (Mandatory on Commit & Push)` e `## 🧪 [ALL AGENTS] Mandatory Quality Gates` in `.agents/AGENTS.md` per sancire che **prima di qualsiasi `git commit` e `git push` è obbligatorio eseguire l'intera suite di test (`uv run --with pytest pytest -q --tb=short --maxfail=2`) e i check di linting (`ruff check` / `ruff format --check`) con esito 100% PASS (exit code 0)**.

---

## 3. Strategia di Verifica e Falsificazione (TDD)
- Ogni modifica sarà preceduta da test unitari dedicati (in `tests/test_security_hardening.py` e aggiornamento dei test esistenti) che falliscono (`RED`) sul codice attuale e passano (`GREEN`) dopo l'hardening:
  1. Test redazione credenziali in `ws_call_control(action="monitor")` con URL `rtsps://admin:secret123@1.2.3.4:554/live`.
  2. Test limite dimensione payload, rate limiting e cap LRU 32 sessioni in `ws_audio_tx`.
  3. Test anti-OOM su `_read_sip_msg` con header `> 16 KB` senza `\r\n\r\n` e con `Content-Length > 64 KB` o negativo.
  4. Test filtro IP UDP su `_video_rx_loop`, `_audio_rx_loop` (anti-hijacking Symmetric RTP) e `AveSipSession.datagram_received`.
  5. Test sanitizzazione path traversal (`../../etc/passwd`) su `device_id` per il file SDP.
  6. Test registrazione servizi con schema Voluptuous in `_async_register_services`.
  7. Test `parse_gvs_udp_packet` con `payload_length < 16` che solleva `ValueError` anziché `IndexError`.
