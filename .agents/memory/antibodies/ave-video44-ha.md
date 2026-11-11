# Crash Antibodies — Ave-video44-HA (SIP/WebRTC Intercom & Lovelace Card)

## [AB-AVE-001] WebAudio Autoplay Resume & Dynamic RX Jitter Buffer
- **Target Files**: `custom_components/ave_video44/**/*.js`, `custom_components/ave_video44/**/*.py`, `www/**/*.js`
- **Root Cause**: I browser mobile/WebView bloccano `AudioContext` in stato `suspended` se non ripreso dentro un gesto utente, e un buffer statico causa underrun o latenza crescente sull'audio citofonico PCM/G.711.
- **Invariant**: Invocare sempre `await audioCtx.resume()` sul gesto di risposta/apertura chiamata e mantenere il ring-buffer RX con riallineamento dinamico del jitter.
- **onFailure Mandate**: Chiudere e rilasciare `MediaStreamTrack` e `AudioContext` nel blocco `finally` a fine chiamata.
- **Forbidden Regex**: `new\s+AudioContext\(\)\s*;\s*//\s*no\s+resume`

## [AB-AVE-002] Lovelace `ll-rebuild` Storm Prevention & Cache-Busting
- **Target Files**: `custom_components/ave_video44/**/*.js`, `www/**/*.js`
- **Root Cause**: Emettere `ll-rebuild` o ricreare il DOM WebRTC ad ogni aggiornamento di `hass` (`set hass(obj)`) distrugge lo stream video attivo e congela la UI di Home Assistant.
- **Invariant**: Il setter `set hass(value)` deve aggiornare il DOM solo se cambiano gli stati delle entità monitorate dal citofono, mai durante lo streaming attivo.
- **onFailure Mandate**: Conservare il riferimento al player video attivo durante gli aggiornamenti di stato non correlati.
- **Forbidden Regex**: `set\s+hass\s*\([^)]*\)\s*\{\s*this\.render\(\)`

## [AB-AVE-003] WebSocket RTSP Redaction, SIP TCP/UDP Bounds & Pre-Commit Test Gate
- **Target Files**: `custom_components/ave_video44/websocket_api.py`, `custom_components/ave_video44/core/sip_session.py`, `custom_components/ave_video44/core/protocol.py`
- **Root Cause**: Risposte WebSocket `action=monitor` con credenziali RTSP in chiaro, letture SIP TCP senza tetto su header/`Content-Length`, e socket UDP RTP in chiaro (`RTP/AVP`) che accettano pacchetti da IP arbitrari sulla LAN espongono l'impianto domestico a leak di credenziali, OOM e hijacking audio.
- **Invariant**: Mascherare sempre le credenziali in `rtsp_url` prima dell'invio via WebSocket, imporre `MAX_SIP_HEADER_BYTES`/`MAX_SIP_CONTENT_LENGTH` in `_read_sip_msg`, filtrare gli IP sorgente UDP con `_is_trusted_udp_source` solo su flussi `RTP/AVP` non cifrati (e `AveSipSession` LAN), ed eseguire sempre l'intera suite `pytest` prima di ogni `git commit` / `git push`.
- **onFailure Mandate**: Scartare i frame UDP `RTP/AVP` da IP non autorizzati e svuotare `_rx_buf` sollevando `ValueError` su messaggi SIP fuori limite.
- **Forbidden Regex**: `send_result\([^)]*"rtsp_url"\s*:\s*rtsp_url\s*\)`

## [AB-AVE-005] Cloud SRTP (`RTP/SAVP`) Relay IP Asymmetry & Symmetric RTP (RFC 4961)
- **Target Files**: `custom_components/ave_video44/core/sip_session.py`
- **Root Cause**: In GVS Cloud (`eu.open-sips.gvs-icloud.com`), il `200 OK` SDP spesso riporta in `c=IN IP4` l'IP privato del monitor interno o un IP di signaling diverso dagli IP pubblici dei relay `rtpproxy` da cui arrivano i pacchetti UDP audio/video SRTP. Filtrare `_video_sock` o `RTP/SAVP` su `_audio_sock` tramite `addr[0] == self._remote_ip` scarta il 100% del video e impedisce il Symmetric RTP learning dell'audio.
- **Invariant**: Per i flussi `RTP/SAVP` (SRTP), l'autenticazione del mittente DEVE avvenire crittograficamente tramite HMAC-SHA1 (`_decrypt_srtp_packet` con `hmac.compare_digest` per l'audio e demuxer SRTP FFmpeg per il video) PRIMA di aggiornare `(self._remote_ip, self._remote_audio_port)` via Symmetric RTP, senza pre-filtrare l'IP sorgente UDP rispetto al `c=IN IP4` dell'SDP iniziale. Inoltre, i retry `INVITE` dopo `603 Decline` devono gestire eventuali challenge `401/407` sul nuovo `CSeq`.
- **onFailure Mandate**: Scartare qualsiasi pacchetto `RTP/SAVP` il cui tag HMAC-SHA1 fallisca la verifica prima di toccare `self._remote_ip` o `self._remote_audio_port`.
- **Forbidden Regex**: `while\s+self\._video_sock:\s*\n\s*pkt,\s*addr\s*=\s*self\._video_sock\.recvfrom\(65535\)\s*\n\s*if\s+not\s+self\._is_trusted_udp_source`

## [AB-AVE-004] CI `requirements_test.txt` Parity & `conftest.py` Voluptuous Stub Drift
- **Target Files**: `requirements_test.txt`, `pyproject.toml`, `tests/conftest.py`, `tests/test_repo_governance.py`
- **Root Cause**: L'uso di flag ad-hoc `uv run --with <pkg>` (o pacchetti già presenti in `.venv`) nasconde localmente l'assenza di dipendenze terze parti in `requirements_test.txt`, causando il fallimento della GitHub Action `Validate` (`pip install -r requirements_test.txt`) o l'attivazione di stub incompleti in `tests/conftest.py` (es. `vol.All` / `vol.Length`).
- **Invariant**: Ogni libreria terza parte importata in `custom_components/` o `tests/` deve essere dichiarata sia in `requirements_test.txt` sia in `pyproject.toml`, verificata via AST in `test_ci_requirements_test_parity_with_imports()`, e i test pre-commit devono girare con `uv run --isolated --no-project --with-requirements requirements_test.txt pytest`.
- **onFailure Mandate**: Bloccare il commit se `test_ci_requirements_test_parity_with_imports` o `test_conftest_voluptuous_fallback_stub_contract` falliscono.
- **Forbidden Regex**: `vol_mod\.Schema\s*=\s*lambda`
