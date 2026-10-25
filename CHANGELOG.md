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

## v1.0.2 — 2026-10-25

### 🇬🇧 English

- **Fixed AVE/GVS Cloud Cryptographic Signature (`compute_gvs_sign`)**: Corrected HMAC-SHA1 signature computation according to official AVE Android APK v2.1.2 disassembly, applying mandatory Base64 pre-encoding of sorted query parameters prior to HMAC-SHA1 hashing (`base64(HMAC-SHA1(secret, base64(sorted_query_string))).lower()`).
- **Official APK v2.1.2 REST Endpoints Alignment**:
  - Aligned email login to `POST /usercenter/api/uc/loginToGvs/email` using Retrofit `@QueryMap` URL parameters and form-urlencoded body (`@FieldMap`).
  - Added robust response envelope parsing supporting both `"result"` and `"data"` JSON payloads.
  - Added persistent `JSESSIONID` cookie tracking across authenticated cloud requests.
  - Updated plant and device discovery endpoints to `GET /smarthome/api/home/queryHomeList`, `GET /smarthome/api/quick-display-device/user-current-home`, and `GET /smarthome/api/device/getInfo`.
- **Automatic Session & Plant (`homeId`) Self-Healing**: Enhanced `AveVideo44Coordinator` with automatic credential verification and transparent `homeId` recovery for pre-existing configuration entries without requiring integration reconfiguration.
- **Home Assistant 2025/2026 Options Dialog Compatibility Fix**: Fixed `AttributeError: property 'config_entry' of 'AveVideo44OptionsFlow' object has no setter` when opening the integration Configure dialog, respecting Home Assistant Core's read-only `config_entry` property contract.

### 🇮🇹 Italiano

- **Correzione Firma Crittografica Cloud AVE/GVS (`compute_gvs_sign`)**: Corretto il calcolo della firma HMAC-SHA1 in conformità al decompilato dell'APK ufficiale AVE v2.1.2, applicando la codifica Base64 preliminare della query string ordinata prima del digest HMAC-SHA1 (`base64(HMAC-SHA1(secret, base64(sorted_query_string))).lower()`).
- **Allineamento Endpoint REST con APK Ufficiale v2.1.2**:
  - Allineato il login email su `POST /usercenter/api/uc/loginToGvs/email` con separazione dei parametri query (`@QueryMap`) e corpo form-urlencoded (`@FieldMap`).
  - Supportata la doppia decodifica dell'envelope JSON di risposta (`"result"` e `"data"`).
  - Integrata la persistenza del cookie di sessione `JSESSIONID` per tutte le chiamate successive.
  - Aggiornati gli endpoint di discovery impianto e dispositivi a `GET /smarthome/api/home/queryHomeList`, `GET /smarthome/api/quick-display-device/user-current-home` e `GET /smarthome/api/device/getInfo`.
- **Autoriparazione Sessione e Impianto (`homeId`) nel Coordinator**: `AveVideo44Coordinator` ora rileva e ripristina automaticamente sessioni scadute e il parametro `homeId` per voci di configurazione create con versioni precedenti, senza richiedere la riconfigurazione manuale dell'integrazione.
- **Compatibilità Finestra Opzioni su Home Assistant 2025/2026**: Risolto l'errore `AttributeError: property 'config_entry' of 'AveVideo44OptionsFlow' object has no setter` all'apertura del menu "Configura", rispettando la proprietà in sola lettura `config_entry` introdotta nelle versioni recenti di Home Assistant Core.

## v1.0.1 — 2026-10-24

### 🇬🇧 English

- **Complete Official 8-File Brand Suite (`custom_components/ave_video44/brand/`)**: Integrated crisp high-resolution brand assets derived directly from official AVE Video V44 assets (`ic_login_logo.png` and `icon.png`):
  - Standard & Retina integration icons: `icon.png` (256×256) and `icon@2x.png` (512×512).
  - Dark-mode compatible icons: `dark_icon.png` (256×256) and `dark_icon@2x.png` (512×512).
  - Light-mode brand logos: `logo.png` (240×256) and `logo@2x.png` (480×512) featuring the signature red AVE emblem with dark wordmark.
  - Dark-mode brand logos: `dark_logo.png` (240×256) and `dark_logo@2x.png` (480×512) featuring the red AVE emblem with crisp white wordmark for maximum contrast on dark Home Assistant dashboards.
- **Home Assistant Brand Icons Specification & Translations (`icons.json`)**: Added `icons.json` and standardized `_attr_translation_key` / `_attr_icon` mappings across all 7 supported entity platforms (`lock`, `button`, `binary_sensor`, `sensor`, `event`, `select`, `camera`), providing contextual Material Design Icons for doorbell states, ring conditions, locks, and intercom selectors.
- **Hero Brand Header & Prominent Caution Disclaimer**: Added centered brand header (`<img src=".../logo.png" width="240" />`), streamlined HACS badges, and bilingual active-development / physical access control `[!CAUTION]` disclaimer to `README.md`.

### 🇮🇹 Italiano

- **Suite Ufficiale Completa a 8 File per il Brand (`custom_components/ave_video44/brand/`)**: Integrati gli asset grafici ufficiali ad alta risoluzione ricavati direttamente dall'applicazione AVE Video V44 (`ic_login_logo.png` e `icon.png`):
  - Icone integrazione standard e retina: `icon.png` (256×256) e `icon@2x.png` (512×512).
  - Icone per tema scuro: `dark_icon.png` (256×256) e `dark_icon@2x.png` (512×512).
  - Loghi ufficiali per tema chiaro: `logo.png` (240×256) e `logo@2x.png` (480×512) con emblema geometrico rosso AVE e logotipo nero.
  - Loghi ufficiali per tema scuro: `dark_logo.png` (240×256) e `dark_logo@2x.png` (480×512) con emblema rosso AVE e logotipo bianco ad alto contrasto per le dashboard scure di Home Assistant.
- **Specifiche Icone Native Home Assistant e Traduzioni (`icons.json`)**: Aggiunto il file `icons.json` e normalizzate le mappature `_attr_translation_key` / `_attr_icon` su tutte le 7 piattaforme (`lock`, `button`, `binary_sensor`, `sensor`, `event`, `select`, `camera`), garantendo icone Material Design coerenti per campanello, stati di chiamata, serrature e selettori rubrica.
- **Header Hero con Logo Ufficiale e Disclaimer `[!CAUTION]`**: Inserito il logo centrato (`width="240"`), ripuliti i badge HACS e aggiunto il banner bilingue di avvertenza `[!CAUTION]` in `README.md` per l'uso consapevole su impianti di controllo accessi fisici in fase di sviluppo attivo.

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
