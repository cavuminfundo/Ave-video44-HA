# What is new in AVE Video V44 for Home Assistant

What changes with each update, in plain words. The most recent entries are at
the top. Versions are the "episode" number of the integration: update from
**HACS → AVE Video V44 → Update**.

Every release is written in both languages, English first.

---

# Novità di AVE Video V44 per Home Assistant

Cosa cambia a ogni aggiornamento, spiegato in parole semplici.
Le voci più recenti sono in alto. Le versioni indicano la "puntata"
dell'integrazione: aggiorna da **HACS → AVE Video V44 → Aggiorna**.

## [Non rilasciato]

## v1.0.0 — 2026-10-24

### 🇬🇧 English

- **Initial Release of AVE Video V44 Home Assistant Integration (`ave_video44`)**: First production-grade release providing complete local and cloud integration for AVE Video V44 intercom systems (VI2F-PIT7WF, TS-SMART7, TS-SMART10, and GVS outdoor doorstations).
- **Direct HACS Download Support**: Native HACS integration (`content_in_root: false`) without requiring release asset zip archives, enabling direct repository updates from `cavuminfundo/Ave-video44-HA`.
- **Hybrid Cloud & Local Protocol Architecture**:
  - Cloud REST API with HMAC-SHA1 request signing supporting account password (SHA-256) and email OTP authentication.
  - Persistent MQTTS push listener over TLS (`eu.emqx.gvs-icloud.com:8883`) delivering instant doorbell ring and call events.
  - Local LAN binary protocol engine (`UDP:8300`) with GVS 10-byte magic header (`GVSGVS\xa5\xa5\xa5\xa5`) for direct hardware control.
  - SIP signaling over UDP/TCP (`port 5060`) supporting remote unlock via SIP `INFO` messages.
- **Full-Duplex WebAudio Intercom & 8kHz Resampling Engine**:
  - Custom Lovelace card (`ave-video44-card.js`) automatically registered on startup.
  - Real-time bidirectional voice communication over authenticated Home Assistant WebSockets.
  - Downsampling of browser microphone audio (44.1kHz/48kHz) to 8000 Hz mono 16-bit PCM, bridged to G.711a (PCMA) RTP streams.
  - Legacy Android WebView compatibility with strict exclusion of ES2020+ operators (`?.`, `??`).
- **Comprehensive Home Assistant Native Entities**:
  - `camera`: Live RTSP H.264 video feed compatible with go2rtc and WebRTC.
  - `lock`: Independent pedestrian gate (`Lock 1`) and driveway sliding gate (`Lock 2`) control with automatic pulse relocking.
  - `button`: Quick pulse unlock actions for dashboards and shortcuts.
  - `event`: Doorbell call events (`doorbell_press`, `call_answered`, `call_missed`) with `doorbell` device class.
  - `binary_sensor`: Real-time call in progress and network connectivity monitoring.
  - `sensor`: Call state tracker and duration telemetry.
  - `select`: Inter-apartment intercom directory (`HOUSETOHOUSE`) dynamically populated from integration options.
- **Automated Companion App Blueprint**: Included blueprint (`incoming_call_notification.yaml`) providing high-priority push notifications with visitor snapshot, actionable interactive buttons (Answer, Unlock, Reject), instant deep link (`?ave_call=answer`), and optional multi-room TTS voice announcements.
- **Enterprise Repository Governance & CI/CD**:
  - Automated GitHub Actions suite for HACS validation, Hassfest manifest compliance, card legacy WebView syntax verification, SemVer version synchronization guard, and security dependency auditing (`pip-audit`).
  - Automated GitHub Release workflow triggered on `vX.Y.Z` tags with automated bilingual changelog extraction.
  - Strict zero plaintext secrets policy and sanitized diagnostics export (`diagnostics.py`).

### 🇮🇹 Italiano

- **Rilascio Iniziale dell'Integrazione AVE Video V44 per Home Assistant (`ave_video44`)**: Primo rilascio di livello industriale per il controllo completo, sia locale che cloud, dei sistemi videocitofonici AVE Video V44 (serie VI2F-PIT7WF, TS-SMART7, TS-SMART10 e posti esterni AVE/GVS).
- **Supporto Download Diretto HACS**: Integrazione HACS nativa (`content_in_root: false`) senza necessità di archivio zip di release, consentendo aggiornamenti diretti dal repository `cavuminfundo/Ave-video44-HA`.
- **Architettura Ibrida Cloud e Protocollo Locale**:
  - Client REST API cloud asincrono con firma dei parametri HMAC-SHA1, supporto autenticazione con password (SHA-256) e codice OTP via email.
  - Listener push MQTTS persistente su TLS (`eu.emqx.gvs-icloud.com:8883`) per la notifica istantanea degli eventi di suoneria e stato chiamata.
  - Motore di protocollo binario su rete locale LAN (`UDP:8300`) con header magico GVS a 10 byte (`GVSGVS\xa5\xa5\xa5\xa5`) per controllo diretto dei dispositivi.
  - Segnalazione SIP su porta UDP/TCP `5060` con supporto per apertura serratura remota tramite messaggi SIP `INFO`.
- **Interfono WebAudio Full-Duplex e Motore di Ricampionamento 8kHz**:
  - Card Lovelace personalizzata (`ave-video44-card.js`) registrata automaticamente all'avvio.
  - Comunicazione vocale bidirezionale in tempo reale tramite WebSocket autenticato nativo di Home Assistant.
  - Ricampionamento dell'audio microfonico da 44.1kHz/48kHz a 8000 Hz mono PCM a 16 bit, traslato in stream RTP G.711a (PCMA).
  - Piena compatibilità con WebView Android legacy grazie all'esclusione rigorosa di operatori moderni incompatibili (`?.`, `??`).
- **Piattaforme di Entità Native Home Assistant**:
  - `camera`: Streaming video live RTSP H.264 compatibile con go2rtc e WebRTC.
  - `lock`: Controllo indipendente del cancelletto pedonale (`Lock 1`) e del cancello carraio (`Lock 2`) con auto-ripristino impulsivo dello stato.
  - `button`: Pulsanti per apertura impulsiva immediata da dashboard e widget.
  - `event`: Notifica eventi campanello (`doorbell_press`, `call_answered`, `call_missed`) con device class `doorbell`.
  - `binary_sensor`: Sensori di chiamata in corso e connettività online dei dispositivi.
  - `sensor`: Monitoraggio stato chiamata citofonica e durata conversazione.
  - `select`: Rubrica interni intercom multi-appartamento (`HOUSETOHOUSE`) configurabile direttamente dalle opzioni.
- **Blueprint per Notifiche Interattive Smartphone**: Template di automazione incluso (`incoming_call_notification.yaml`) con invio notifica push ad alta priorità, fermo immagine del visitatore, pulsanti rapidi (Rispondi, Apri Cancello, Rifiuta), deep link automatico (`?ave_call=answer`) e annunci vocali TTS su smart speaker.
- **Governance del Repository e CI/CD**:
  - Suite GitHub Actions completa per validazione HACS, conformità manifest Hassfest, verifica sintassi WebView della card, sincronizzazione SemVer e audit delle vulnerabilità di sicurezza (`pip-audit`).
  - Workflow di rilascio automatico attivato dal push di tag `vX.Y.Z` con estrazione automatica delle note bilingui dal changelog.
  - Politica di riservatezza a zero credenziali in chiaro e diagnostica completamente anonimizzata (`diagnostics.py`).
