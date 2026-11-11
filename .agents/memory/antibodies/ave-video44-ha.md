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
- **Root Cause**: Risposte WebSocket `action=monitor` con credenziali RTSP in chiaro, letture SIP TCP senza tetto su header/`Content-Length`, e socket UDP che accettano pacchetti da IP arbitrari sulla LAN espongono l'impianto domestico a leak di credenziali, OOM e hijacking audio/video.
- **Invariant**: Mascherare sempre le credenziali in `rtsp_url` prima dell'invio via WebSocket, imporre `MAX_SIP_HEADER_BYTES`/`MAX_SIP_CONTENT_LENGTH` in `_read_sip_msg`, filtrare gli IP sorgente UDP con `_is_trusted_udp_source`, ed eseguire sempre l'intera suite `pytest` prima di ogni `git commit` / `git push`.
- **onFailure Mandate**: Scartare i frame UDP da IP non autorizzati e svuotare `_rx_buf` sollevando `ValueError` su messaggi SIP fuori limite.
- **Forbidden Regex**: `send_result\([^)]*"rtsp_url"\s*:\s*rtsp_url\s*\)`
