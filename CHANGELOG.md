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

## v1.2.11 — 2026-10-26

### 🇬🇧 English

- **Video Diagnostic Telemetry & Jitter Analysis**:
  - Source frame rate monitoring: tracks incoming RTP packets and counts video frames using RTP marker bit (`0x80`), logging `src_fps` and `max_pkt_gap_ms` every 5 seconds.
  - FFmpeg MJPEG gap tracking: measures inter-frame delivery intervals, calculating maximum and 95th-percentile gaps (`max_gap_ms`, `p95_gap_ms`) to detect decoder stuttering.
  - MJPEG streaming telemetry: tracks served frames to HTTP clients and inter-write send intervals (`max_send_gap_ms`) including network write/drain await latency in `camera.py`.
  - FFmpeg command logging: logs sanitized FFmpeg spawn command line at debug level.

### 🇮🇹 Italiano

- **Telemetria Diagnostica Frame Video e Analisi Jitter**:
  - Monitoraggio frame rate sorgente: analizza i pacchetti RTP in ingresso rilevando i frame video tramite RTP marker bit (`0x80`), registrando `src_fps` e `max_pkt_gap_ms` ogni 5 secondi.
  - Tracciamento intervalli MJPEG FFmpeg: calcola l'intervallo tra fotogrammi consecutivi estratti da FFmpeg con valori massimo e 95° percentile (`max_gap_ms`, `p95_gap_ms`) per diagnosticare scatti e jitter nel decoder.
  - Telemetria streaming MJPEG: traccia i frame inviati ai client HTTP e l'intervallo massimo tra scritture consecutive (`max_send_gap_ms`), includendo la latenza di await di write/drain in `camera.py`.
  - Log comando FFmpeg: registra a livello debug la riga di comando sanitizzata di avvio processo FFmpeg.

## v1.2.10 — 2026-10-26

### 🇬🇧 English

- **High-Performance 25 FPS Video & Real-Time MJPEG Streaming**:
  - Upgraded video target rate from 15 FPS to 25 FPS (`MJPEG_TARGET_FPS = 25`) in FFmpeg video filter pipeline.
  - Intercom card switches to native Home Assistant MJPEG video stream (`camera_proxy_stream`) during active calls and monitoring instead of snapshot polling.
  - Ultra-responsive UDP relay loop: yields immediately (`asyncio.sleep(0)`) when RTP video packets arrive and applies minimal backoff only when socket is empty, eliminating artificial forwarding latency.
  - Server-side MJPEG stream deduplication: guarantees each decoded frame is served exactly once (`next_seq > last_seq`), preventing stale duplicate frames during stream timeouts.

### 🇮🇹 Italiano

- **Video ad Alte Prestazioni a 25 FPS e Streaming MJPEG Nativo**:
  - Incrementato il frame rate video da 15 a 25 FPS (`MJPEG_TARGET_FPS = 25`) nella pipeline di decodifica FFmpeg.
  - Card citofonica aggiornata per usare lo stream MJPEG nativo di Home Assistant (`camera_proxy_stream`) durante chiamate e monitoraggio attivo al posto del polling snapshot.
  - Loop di relay UDP ad alta reattività: yield immediato (`asyncio.sleep(0)`) alla ricezione di pacchetti RTP video e backoff minimo solo a socket vuoto, eliminando latenze artificiali di inoltro.
  - Deduplicazione frame nello stream MJPEG: ogni nuovo frame decodificato viene servito una sola volta (`next_seq > last_seq`), prevenendo l'invio di frame duplicati o obsoleti sui timeout.

## v1.2.9 — 2026-10-26

### 🇬🇧 English

- **Media & Signaling Diagnostic Debug Telemetry**:
  - Added low-frequency, non-invasive `_LOGGER.debug` counters (every 5 seconds) for inbound SRTP video packets and byte rates.
  - Added real-time MJPEG frame counter and instantaneous FPS rate logging in the frame extractor loop.
  - Added audio RX packet counter logging and audio TX queued vs. sent metrics in SIP session and WebSocket streaming APIs.
  - Added session startup diagnostics for local and remote audio/video ports and negotiated SDP audio payload types.
  - Enhanced remote SIP `BYE` handling with safe header diagnostics (such as `Reason`, `CSeq`, `User-Agent`) without credentials or sensitive data.
  - No functional changes.

### 🇮🇹 Italiano

- **Diagnostica e Telemetria Debug per Flussi Multimediali e Segnalazione**:
  - Aggiunti contatori diagnostici `_LOGGER.debug` a bassa frequenza (ogni 5 secondi) per pacchetti e byte SRTP video in ingresso.
  - Aggiunto conteggio frame JPEG estratti con calcolo del rate FPS istantaneo nel loop di decodifica MJPEG.
  - Aggiunto conteggio pacchetti audio RX e tracciamento frame TX accodati rispetto a trasmessi nella sessione SIP e nelle API WebSocket audio.
  - Aggiunti log di avvio sessione con porte locali/remote audio e video e payload type SDP audio negoziato.
  - Migliorato il tracciamento dei messaggi SIP `BYE` remoti registrando gli header informativi (`Reason`, `CSeq`, `User-Agent`) senza esporre credenziali o dati sensibili.
  - Nessuna variazione funzionale.

## v1.2.8 — 2026-10-25

### 🇬🇧 English

- **Lovelace Card UI Streamlining**:
  - Removed redundant duplicate "Chiudi" hangup button (`#btnHangup`) during outdoor station video monitoring sessions, preserving a single clean close action via `#btnCallIntercom`.
  - Completely removed the video feed overlay banner (`#callerBanner`) and its styles, providing a 100% unobstructed, crystal-clear camera view across all card states.

### 🇮🇹 Italiano

- **Snellimento Interfaccia Card Lovelace**:
  - Rimosso il doppio pulsante "Chiudi" in alto (`#btnHangup`) durante le sessioni di monitoraggio del posto esterno, mantenendo un unico e chiaro comando di chiusura tramite `#btnCallIntercom`.
  - Rimossa completamente la sovraimpressione video (`#callerBanner`) e i relativi stili, offrendo una vista telecamera pulita al 100% e priva di ostacoli visivi in tutti gli stati della card.

## v1.2.7 — 2026-10-25

### 🇬🇧 English

- **Dynamic Intercom Call Button & Hangup Toggle**:
  - Dynamically switches the intercom call button (`#btnCallIntercom`, "Chiama") into a red hangup button ("Chiudi" / "Termina" / "Rifiuta") during active call or monitoring sessions (`_inCall`).
  - Pressing the button while in a call triggers `_hangup()`, preventing accidental duplicate call requests.
  - Automatically disables the intercom address book selector (`#intercomSelect`) during active sessions and disables both controls during the connection phase (`loading`).

### 🇮🇹 Italiano

- **Commutazione Dinamica Tasto Chiamata Intercom e Chiusura**:
  - Commutazione dinamica del pulsante `#btnCallIntercom` ("Chiama") in un pulsante rosso di chiusura ("Chiudi" / "Termina" / "Rifiuta") durante una chiamata o sessione di monitoraggio attiva (`_inCall`).
  - La pressione del pulsante durante la chiamata invoca `_hangup()`, prevenendo l'invio accidentale di chiamate duplicate.
  - Disabilitazione automatica del selettore rubrica `#intercomSelect` durante le sessioni attive e disabilitazione di entrambi i controlli durante la fase di connessione (`loading`).

## v1.2.6 — 2026-10-25

### 🇬🇧 English

- **SIP Session Liveness, Remote BYE Listener & 2-Wire Bus Cooldown**:
  - Fixed SIP session lockups (`TimeoutError` / `603 Decline`) occurring after closing a video stream or reopening the Android Companion App.
  - Implemented RTP packet liveness tracking (`last_rtp_ts`) to proactively detect dead media channels.
  - Added background listener for remote SIP `BYE` messages to promptly terminate sessions when the outdoor station or server ends the dialog.
  - Added automatic cleanup of orphaned SIP sessions if no client frame reads occur for 20 seconds.
  - Enforced a mandatory 3.0-second 2-wire bus cooldown interval between consecutive SIP sessions, preventing OpenSIPS re-invite rejections while the physical bus discharges.
- **Mobile Companion App Lifecycle & Request Abort**:
  - Eliminated Lovelace *"Configuration error"* (`Errore di configurazione`) dialogs when switching or backgrounding the Android Companion App while video is playing.
  - Integrated `AbortController` to cancel in-flight HTTP frame fetches immediately upon disconnect.
  - Hooked `visibilitychange` and `disconnectedCallback` events in `ave-video44-card.js` for graceful session hangup and stream teardown.
- **15 FPS Smooth Live Video**:
  - Increased video playback rate from ~3 FPS to a smooth 15 FPS.
  - Optimized FFmpeg pipeline parameters (`fps=15`, `-fflags nobuffer -flags low_delay`).
  - Tuned the card's asynchronous frame rendering loop to a 65ms pipelined cadence.
- **Low-Latency Gate & Door Cold Unlock**:
  - Drastically reduced cold unlock latency on 2-wire installations by waiting only for the SIP `200 OK` handshake (`wait_for_sip_connected`) followed by a brief 0.35s bus stabilization delay, rather than awaiting full H.264 video frame decoding.

### 🇮🇹 Italiano

- **Tracciamento Liveness SIP, Ascolto BYE Remoto e Cooldown Bus 2 Fili**:
  - Risolti i blocchi della sessione SIP (`TimeoutError` / `603 Decline`) che si verificavano dopo la chiusura dello stream video o alla riapertura dell'app Android.
  - Introdotto il tracciamento della liveness dei pacchetti RTP (`last_rtp_ts`) per rilevare tempestivamente la caduta dei canali multimediali.
  - Implementato l'ascolto in background dei messaggi SIP `BYE` remoti per rilasciare immediatamente il dialogo quando il posto esterno o il server chiudono la chiamata.
  - Aggiunto l'auto-rilascio delle sessioni orfane dopo 20 secondi di inattività delle letture dei frame da parte dei client.
  - Introdotto un intervallo di cooldown obbligatorio di 3.0 secondi sul bus 2 fili tra sessioni SIP consecutive, evitando che OpenSIPS rifiuti nuovi inviti mentre il bus fisico si scarica.
- **Ciclo di Vita Companion App Mobile e Abort delle Richieste**:
  - Eliminato il popup Lovelace *"Errore di configurazione"* causato dalla chiusura e riapertura dell'app Companion Android durante lo streaming attivo.
  - Integrato `AbortController` in `ave-video44-card.js` per annullare istantaneamente le richieste HTTP di frame in volo al momento della disconnessione.
  - Gestiti gli eventi `visibilitychange` e `disconnectedCallback` per eseguire un hangup pulito e terminare lo stream alla messa in background dell'app.
- **Video Live Fluido a 15 FPS**:
  - Incrementata la fluidità dello streaming video live da circa 3 FPS a 15 FPS stabili.
  - Ottimizzati i parametri FFmpeg (`fps=15`, `-fflags nobuffer -flags low_delay`).
  - Ottimizzato il loop asincrono di rendering dei frame nella card Lovelace a un intervallo di 65 ms.
- **Sblocco Cancello e Cancelletto a Bassa Latenza da Riposo**:
  - Ridotta drasticamente la latenza di sblocco a riposo (cold unlock) sui sistemi a 2 fili attendendo unicamente il `200 OK` del SIP (`wait_for_sip_connected`) e una breve stabilizzazione del bus di 0.35s, invece di attendere la decodifica del flusso video completo.

## v1.2.5 — 2026-10-25

### 🇬🇧 English

- **2-Wire Bus Relay Unlock via `commandDevice` (`functionId="23"` / `"24"`) & Auto-Wake Handshake**:
  - Fixed failure to actuate Pedestrian Gate (Lock 1) and Driveway Gate (Lock 2) on 2-wire `TS-SMART` indoor monitors (`VI2F-PIT7WF`, `TS-SMART7xx`, `TS-SMART10xx`, `protocol="0"`).
  - Implemented the proprietary cloud command endpoint `POST /smarthome/api/device/command/control` extracted from Android bytecode (`LinphoneTalkBack.unlock`):
    - Pedestrian gate unlock: `functionId="23"` with JSON payload `value='{"outDoorNumber":"1","lockStatus":1}'`.
    - Driveway sliding gate unlock: `functionId="24"` with JSON payload `value='{"outDoorNumber":"1","lockStatus":1}'`.
  - Added temporary SIP/SRTP auto-wake handshake: when an unlock command is initiated in idle state (`call_state === "idle"`), the integration briefly wakes the unpowered 2-wire outdoor station to energize its internal relay coil on the bus before pulsing the unlock command.
- **In-Call Dual Unlock Controls (`ave-video44-card.js`)**:
  - Added the **Apri Cancello** (Driveway Gate) button during active video monitoring and call states, providing direct dual-lock control alongside **Apri Cancelletto** (Pedestrian Gate).

### 🇮🇹 Italiano

- **Sblocco Relè Bus 2 Fili via `commandDevice` (`functionId="23"` / `"24"`) e Handshake di Auto-Risveglio**:
  - Risolto il mancato azionamento di Cancelletto (Serratura 1) e Cancello Carraio (Serratura 2) sui monitor `TS-SMART` a 2 fili (`VI2F-PIT7WF`, `TS-SMART7xx`, `TS-SMART10xx`, `protocol="0"`).
  - Implementato l'endpoint cloud proprietario `POST /smarthome/api/device/command/control` estratto dal bytecode Android (`LinphoneTalkBack.unlock`):
    - Sblocco cancelletto pedonale: `functionId="23"` con payload JSON `value='{"outDoorNumber":"1","lockStatus":1}'`.
    - Sblocco cancello carraio: `functionId="24"` con payload JSON `value='{"outDoorNumber":"1","lockStatus":1}'`.
  - Introdotto l'handshake di auto-risveglio temporaneo via SIP/SRTP: quando il comando apriporta viene impartito a riposo (`idle`), l'integrazione risveglia brevemente il posto esterno per alimentare la bobina del relè sul bus 2 fili prima di trasmettere l'impulso di sblocco.
- **Controlli Doppia Serratura Durante la Chiamata (`ave-video44-card.js`)**:
  - Aggiunto nella card Lovelace il pulsante **Apri Cancello** (carraio) anche durante il monitoraggio video e la conversazione attiva, accanto ad **Apri Cancelletto** (pedonale).

## v1.2.4 — 2026-10-25

### 🇬🇧 English

- **Pipelined TCP SIP Parser & Concurrent Wake Lock**:
  - Fixed TCP framing bug in `CloudSipMediaSession._read_sip_msg()` that dropped subsequent SIP frames when multiple messages (`100 Giving it a try`, `180 Ringing`, and `200 OK`) arrived packed in the same TCP segment.
  - Maintained consistent `Call-ID` and `tag` values across SIP `REGISTER` challenges and authentication responses.
  - Introduced an `asyncio.Lock` in `async_wake_camera` to serialize concurrent OpenSIPS connection attempts from rapid button taps.
- **Mobile WebView / VPN Frame Loop & Outbound Intercom Routing**:
  - Replaced native `multipart/x-mixed-replace` on `<img class="hidden">` with an asynchronous `fetch` -> `Blob` -> `URL.createObjectURL` frame loop against `/api/camera_proxy/`, eliminating black screen stalls on Android WebView / iOS Companion apps and WireGuard/Tailscale VPN connections where `onload` failed to fire.
  - Fixed intercom call button target matching for entries formatted like `"1 (Citofono)"` in `select.rubrica_interni`.
  - Hidden the *"Rispondi"* (Answer) button during outgoing call states (`call_state === "ringing"` when initiated locally).

### 🇮🇹 Italiano

- **Parser SIP TCP Pipelined e Lock di Risveglio Concorrente**:
  - Risolto il bug di framing TCP in `CloudSipMediaSession._read_sip_msg()` che scartava i messaggi SIP successivi quando `100 Giving it a try`, `180 Ringing` e `200 OK` giungevano concatenati all'interno del medesimo segmento TCP.
  - Mantenuti `Call-ID` e `tag` coerenti durante la procedura di challenge-response per la registrazione SIP (`REGISTER`).
  - Introdotto un `asyncio.Lock` in `async_wake_camera` per serializzare i tentativi di connessione concorrenti verso OpenSIPS a fronte di tocchi rapidi e ripetuti.
- **Rendering Frame Loop con Blob URL per WebView Mobile/VPN e Routing Interfono in Uscita**:
  - Sostituito lo streaming diretto `multipart/x-mixed-replace` su tag `<img class="hidden">` con un loop asincrono `fetch` -> `Blob` -> `URL.createObjectURL` su `/api/camera_proxy/`, risolvendo il problema del riquadro nero su Android WebView, iOS Companion app e VPN (WireGuard/Tailscale) in cui l'evento `onload` non veniva scatenato.
  - Corretto il parsing dell'estensione citofonica per voci di rubrica con formato `"1 (Citofono)"` sul pulsante *Chiama*.
  - Nascosto il pulsante *Rispondi* durante le chiamate in uscita avviate dalla postazione interna.

## v1.2.3 — 2026-10-25

### 🇬🇧 English

- **Frontend-Backend Stream Synchronization & Multipart Boundary Fix**:
  - Resolved race condition when clicking *"Attiva Video"* in `ave-video44-card.js`: the frontend previously opened `/api/camera_proxy_stream` before the Cloud SIP/SRTP handshake settled, resulting in `HTTP 502 Bad Gateway`.
  - Added `async_wait_for_wake` synchronization in `AveVideo44Camera` to hold stream initialization until the media session state transitions from standby to active.
  - Aligned the MJPEG stream boundary to Home Assistant Core's native `multipart/x-mixed-replace; boundary=--frameboundary` specification.
  - Eliminated superfluous `control_monitoring` API calls (port 8322 RTSPS) for 2-wire Cloud SIP `TS-SMART` systems (`protocol="0"`).
- **Non-Blocking SDP I/O & Intercom Self-URI Filtering**:
  - Moved temporary SDP descriptor file I/O to `asyncio.to_thread`, preventing event loop blocking warnings during SIP media session bootstrap.
  - Filtered the indoor monitor's own SIP proxy URI from intercom auto-discovery to prevent loopback entries in `select.rubrica_interni`.

### 🇮🇹 Italiano

- **Sincronizzazione Stream Frontend-Backend e Allineamento Boundary Multipart**:
  - Risolta la race condition al click su *"Attiva Video"* in `ave-video44-card.js`: il frontend tentava di aprire `/api/camera_proxy_stream` prima del completamento dell'handshake SIP/SRTP ricevendo `HTTP 502 Bad Gateway`.
  - Aggiunto il coordinamento asincrono `async_wait_for_wake` su `AveVideo44Camera` per attendere che la sessione multimediale sia pienamente stabilita prima di servire i frame.
  - Allineato il boundary del flusso MJPEG allo standard nativo di Home Assistant Core (`multipart/x-mixed-replace; boundary=--frameboundary`).
  - Eliminata la chiamata superflua a `control_monitoring` (porta 8322 RTSPS) per i dispositivi Cloud SIP serie `TS-SMART` (`protocol="0"`).
- **I/O SDP Non Bloccante e Filtraggio Self-URI Rubrica Interfono**:
  - Spostata la scrittura su disco del descrittore SDP temporaneo su `asyncio.to_thread` per eliminare i warning di blocco dell'event loop di Home Assistant.
  - Filtrato l'URI SIP proxy del monitor stesso durante l'auto-discovery della rubrica interfono, evitando voci di loopback in `select.rubrica_interni`.

## v1.2.2 — 2026-10-25

### 🇬🇧 English

- **Cloud SIP + SRTP H.264 Video Engine (`CloudSipMediaSession`)**:
  - Fixed live video streaming for 2-wire bus `TS-SMART` indoor monitors (`VI2F-PIT7WF`, `TS-SMART7xx`, `TS-SMART10xx`, `protocol="0"`), which do not support RTSPS on port 8322 but require authenticated SIP `INVITE` signaling to `eu.open-sips.gvs-icloud.com:5060`.
  - Implemented the 14 proprietary GVS/AVE custom SIP headers, including mandatory `enableVideo: 1`, `proxyDeviceId`, and `proxyFlag: 1`.
  - Mandatory SRTP negotiation (`RTP/SAVP` with `AES_CM_128_HMAC_SHA1_80` crypto attribute) for secure real-time media ingestion.
  - Symmetric RTP NAT hole-punching: transmits initial probe packets to establish bi-directional firewall pinholes so the cloud media server can deliver inbound H.264 RTP packets to Home Assistant.
  - Low-latency H.264 Annex-B depacketization and FFmpeg `image2pipe` transcoding directly into JPEG frames.
- **Camera Entity Instant MJPEG & Still Frame**:
  - `AveVideo44Camera` now delivers instant JPEG frames decoded directly from the active SIP/SRTP session for both live `multipart/x-mixed-replace` streaming in the Bubble Card and `async_camera_image` snapshot requests.
- **MQTT TLS Port 18883 & Home Topic Subscriptions**:
  - Updated cloud MQTTS connection to port `18883` and added subscriptions to plant-level topics `smarthome/device/{homeId}` and `smarthome/device/status/{homeId}` for reliable ring and monitoring state event delivery.

### 🇮🇹 Italiano

- **Cloud SIP + SRTP H.264 Video Engine (`CloudSipMediaSession`)**:
  - Risolto lo streaming video sui videocitofoni 2 fili serie `TS-SMART` (`VI2F-PIT7WF`, `TS-SMART7xx`, `TS-SMART10xx`, `protocol="0"`), i quali non utilizzano RTSPS sulla porta `8322` ma richiedono una sessione SIP `INVITE` autenticata verso `eu.open-sips.gvs-icloud.com:5060`.
  - Implementati i 14 header SIP proprietari GVS/AVE, incluso `enableVideo: 1` obbligatorio, `proxyDeviceId` e `proxyFlag: 1`.
  - Negoziazione SRTP obbligatoria (`RTP/SAVP` con suite `AES_CM_128_HMAC_SHA1_80`) per l'acquisizione sicura dei flussi multimediali in tempo reale.
  - NAT hole-punching RTP simmetrico: invio di pacchetti probe iniziali per aprire i varchi nei firewall stateful e router NAT, consentendo al media server cloud di instradare i pacchetti RTP H.264 verso Home Assistant.
  - Depacketizzazione H.264 Annex-B e decodifica a bassissima latenza tramite FFmpeg `image2pipe` direttamente in frame JPEG continui.
- **Camera Entity Instant MJPEG & Still Frame**:
  - `AveVideo44Camera` serve ora istantaneamente i frame JPEG decodificati dalla sessione SIP/SRTP sia per lo streaming live `multipart/x-mixed-replace` nella Bubble Card sia per gli snapshot `async_camera_image`.
- **Porta MQTT TLS 18883 e Sottoscrizioni Topic di Impianto**:
  - Aggiornata la connessione MQTTS cloud sulla porta `18883` e introdotte le sottoscrizioni ai topic di impianto `smarthome/device/{homeId}` e `smarthome/device/status/{homeId}` per la ricezione tempestiva degli eventi di suoneria e monitoraggio.

## v1.2.1 — 2026-10-25

### 🇬🇧 English

- **Fixed Cold F5 Reload Configuration Error on `Videocitofono` Dashboard**:
  - Resolved `"Errore di configurazione: Elemento personalizzato inesistente: ave-video44-card"` warning on browser F5 reload by using a standard Lovelace view layout with single-card desktop expansion (`max-width: 780px`) instead of `panel: true` (`hui-panel-view`), ensuring Home Assistant's `ll-rebuild` event is reliably dispatched once custom element scripts finish evaluating.
  - Implemented non-blocking executor thread offloading (`hass.async_add_executor_job`) for storage dashboard synchronization to prevent event loop blocking.
- **Fixed Idle Video Viewport & Camera Wake Control Visibility**:
  - Added strict `isVideoActive` guard ensuring the idle standby graphic (`#videoPlaceholder`) is not prematurely hidden by snapshot image attempts when the 2-wire camera is unpowered.
  - Added an interactive "Attiva Video" bubble button directly inside `#videoPlaceholder` allowing one-tap camera wake-up directly from the video area.
  - Wrapped hangup button text inside a dedicated `#hangupLabel` element to preserve the telephone hangup icon across call lifecycle transitions.

### 🇮🇹 Italiano

- **Risolto Errore di Configurazione su Ricarica F5 della Dashboard `Videocitofono`**:
  - Risolto il messaggio `"Errore di configurazione: Elemento personalizzato inesistente: ave-video44-card"` al ricaricamento forzato della pagina (F5) migrando la vista della plancia da `panel: true` (`hui-panel-view`) a una vista standard con espansione singola scheda centrata a 780px, garantendo la ricezione costante dell'evento `ll-rebuild` dopo l'inizializzazione dello script nel browser.
  - Sincronizzazione non bloccante della plancia in `.storage` demandata al thread executor (`hass.async_add_executor_job`) per salvaguardare la reattività dell'event loop.
- **Correzione Viewport Video a Riposo e Controllo Risveglio Telecamera**:
  - Introdotto il controllo `isVideoActive` per evitare che tentativi di caricamento di `cameraStreamImg` nascondano erroneamente il placeholder a riposo (`#videoPlaceholder`) quando la telecamera a 2 fili è disalimentata.
  - Inserito un pulsante a bolla interattivo "Attiva Video" direttamente all'interno dell'area `#videoPlaceholder` per risvegliare il posto esterno con un tocco sullo schermo.
  - Isolato il testo del pulsante di chiusura chiamata in `#hangupLabel` per preservare stabilmente l'icona del ricevitore telefonico durante le transizioni di stato.

## v1.2.0 — 2026-10-25

### 🇬🇧 English

- **Live RTSPS Cloud Video Streaming & FFmpeg Camera Proxy**:
  - Implemented secure TLS RTSPS live video streaming (`rtsps://{user}:{pwd}@{domain}:8322/stream/1/{deviceId}/0/{targetNum}`) using cloud basic credentials and dedicated port 8322.
  - Dynamically updates active stream endpoints on MQTT `"code": "monitoring"` events (`value.result.serverUrl`).
  - Added FFmpeg MJPEG proxy in `camera.py` (`-rtsp_transport tcp`) for snapshots and live streams, returning `None` when idle to prevent stream errors while 2-wire hardware is unpowered.
  - Graceful monitoring session teardown: sends `action: 3` via `POST /smarthome/api/device-monitoring/monitoring` upon call hangup or monitoring preview closure.
- **Bubble Card UI Redesign & Customizable Card Title (`ave-video44-card.js`)**:
  - Complete card interface redesign inspired by modern **Bubble Card** principles: pill card container (`border-radius: 28px`), circular icon bubbles (`border-radius: 50%`) inside full-pill action buttons (`.bubble-pill-btn`, `border-radius: 999px`), floating status badges, and rounded 16:9 video frame (`border-radius: 22px`).
  - Customizable title (`config.title` / `Titolo Card`), configurable both in YAML and via the visual card editor (`ave-video44-card-editor`, default `"AVE Video V44"`).
  - Responsive multi-device layout: desktop grid (`repeat(auto-fit, minmax(200px, 1fr))`) and mobile-optimized layout constrained to `max-width: 780px` in panel view.
  - Clean video loading states: keeps `<video id="liveVideo">` hidden while empty and automatically retries `cameraStreamImg` during 2-wire wake-up delays.
- **Optional `Videocitofono` Sidebar Dashboard Toggle (`enable_sidebar_panel`)**:
  - Added `enable_sidebar_panel` toggle (default `True`) in Integration Options (**Settings -> Devices & Services -> AVE Video V44 -> Configure -> General settings**).
  - Allows users to show or hide the dedicated `Videocitofono` panel dashboard in the Home Assistant sidebar navigation.
- **On-Demand Camera Wake Button (`button.*_attiva_telecamera` / `wake_camera`) & Lovelace Card Monitor Control**:
  - Added an enabled-by-default Camera Wake button (`button.attiva_telecamera` / `button.posto_esterno_attiva_telecamera`) allowing users to power up and stream the 2-wire outdoor doorstation camera on demand.
  - In 2-wire bus installations, outdoor doorstation cameras are powered down when idle to conserve energy. Waking the camera dispatches `POST /smarthome/api/device-monitoring/monitoring` with `action: 1` (`resolutionLevel: 0`, `monitoringDeviceNumber`), returning an active session `callId`, setting state to `monitoring`, and dynamically acquiring the live RTSP stream URL.
  - The bundled Lovelace card includes an `"Attiva Video"` (`#btnMonitor`) idle control button, triggering on-demand live video with a single click.
- **1-Click Intercom Auto-Discovery & Startup Seeding (`OptionsFlow` & Coordinator)**:
  - Added 1-click **Intercom Auto-Discovery** (`Scopri automaticamente interni e posti esterni (Auto-Discovery)`) as the primary option in integration options (**Settings -> Devices & Services -> AVE Video V44 -> Configure**).
  - Automatically queries `user-current-home`, `monitoring-list`, and local UDP 8300 broadcasts to extract and register room units, extensions (`deviceIntercomInfo`), and doorstation relays (`extraConfig`).
  - Automatically seeds `intercom_book` on startup if empty, immediately providing functional extension listings in `select.rubrica_interni`.
- **Immutable Cache-Bypass Card Static Path (`/ave_video44_card/ave-video44-card.js`)**:
  - Switched the primary Lovelace card static path to `/ave_video44_card/ave-video44-card.js?v=1.2.0` with `cache_headers=False` (retaining backward-compatible alias at `/ave_video44_frontend/`).
  - Eliminates persistent caching issues in mobile Companion App WebViews and Service Workers, ensuring instant delivery of card updates.

### 🇮🇹 Italiano

- **Streaming Cloud Live RTSPS e Proxy Telecamera FFmpeg**:
  - Implementato lo streaming live sicuro TLS RTSPS (`rtsps://{user}:{pwd}@{domain}:8322/stream/1/{deviceId}/0/{targetNum}`) tramite credenziali cloud basic e porta dedicata 8322.
  - Sincronizzazione dinamica dell'endpoint di streaming con gli eventi MQTT `"code": "monitoring"` (`value.result.serverUrl`).
  - Aggiunto proxy FFmpeg MJPEG in `camera.py` (`-rtsp_transport tcp`) per snapshot e streaming live, con restituzione di `None` a riposo per azzerare gli errori di connessione quando il posto esterno a 2 fili è spento.
  - Rilascio corretto della sessione di monitoraggio: invio di `action: 3` via `POST /smarthome/api/device-monitoring/monitoring` alla chiusura dell'anteprima o al termine della conversazione.
- **Riprogettazione Grafica Bubble Card e Titolo Personalizzabile (`ave-video44-card.js`)**:
  - Interfaccia della card completamente ridisegnata ispirata ai canoni estetici **Bubble Card**: contenitore a pillola (`border-radius: 28px`), icone circolari a bolla (`border-radius: 50%`) all'interno dei pulsanti d'azione a pillola (`.bubble-pill-btn`, `border-radius: 999px`), badge di stato fluttuante e viewport video 16:9 arrotondato (`border-radius: 22px`).
  - Titolo della card personalizzabile (`config.title` / `Titolo Card`), modificabile sia da YAML che dall'editor visuale (`ave-video44-card-editor`, predefinito `"AVE Video V44"`).
  - Layout responsive desktop/mobile: griglia desktop (`repeat(auto-fit, minmax(200px, 1fr))`) e ottimizzazione per schermi mobile con larghezza massima limitata a `780px` in visualizzazione pannello (`panel`).
  - Gestione fluida degli stati di caricamento: elemento video nascosto se privo di sorgente e tentativi automatici di ricaricamento di `cameraStreamImg` durante il transitorio di accensione del posto esterno.
- **Controllo Visibilita Dashboard Laterale `Videocitofono` (`enable_sidebar_panel`)**:
  - Nuova opzione `enable_sidebar_panel` (abilitata per impostazione predefinita) in Opzioni Integrazione (**Impostazioni -> Dispositivi e Servizi -> AVE Video V44 -> Configura -> Impostazioni generali**).
  - Consente di mostrare o nascondere la plancia `Videocitofono` nella barra laterale di navigazione di Home Assistant.
- **Pulsante di Risveglio Telecamera On-Demand (`button.*_attiva_telecamera` / `wake_camera`) e Controllo Monitor su Card Lovelace**:
  - Aggiunta un'entità pulsante abilitata per impostazione predefinita (`button.attiva_telecamera` / `button.posto_esterno_attiva_telecamera`) per accendere e visualizzare su richiesta la telecamera del posto esterno a 2 fili.
  - Negli impianti bus a 2 fili le telecamere dei posti esterni sono spente a riposo per risparmio energetico. La pressione del pulsante invia la richiesta cloud `POST /smarthome/api/device-monitoring/monitoring` con `action: 1`, ottenendo l'ID sessione `callId`, portando lo stato su `monitoring` e abilitando dinamicamente il flusso RTSP live.
  - La card Lovelace integrata include ora il pulsante di visualizzazione a riposo `"Attiva Video"` (`#btnMonitor`), avviando lo streaming istantaneamente con un clic.
- **Auto-Discovery Interfoni a 1 Clic e Auto-Seeding all'Avvio (`OptionsFlow` e Coordinator)**:
  - Aggiunta la procedura a 1 clic **Scopri automaticamente interni e posti esterni (Auto-Discovery)** come prima scelta nelle opzioni dell'integrazione (**Impostazioni -> Dispositivi e Servizi -> AVE Video V44 -> Configura**).
  - Scansiona e rileva automaticamente gli interni, le estensioni (`deviceIntercomInfo`) e i posti esterni (`extraConfig`) tramite API cloud e broadcast UDP locali sulla porta 8300.
  - Popolamento automatico (auto-seeding) della rubrica `intercom_book` all'avvio dell'integrazione se vuota, garantendo la disponibilità immediata dei contatti in `select.rubrica_interni`.
- **Nuovo Percorso Risorsa Card Anti-Cache (`/ave_video44_card/ave-video44-card.js`)**:
  - Modificato il percorso statico primario della card Lovelace in `/ave_video44_card/ave-video44-card.js?v=1.2.0` con `cache_headers=False` (mantenendo l'alias retrocompatibile su `/ave_video44_frontend/`).
  - Risolve definitivamente i problemi di caching ostinato delle WebView mobile (Home Assistant Companion App) e dei Service Worker del browser.

## v1.1.2 — 2026-10-25

### 🇬🇧 English

- **Fixed Lovelace Dashboard Custom Element Error (`Custom element doesn't exist: ave-video44-card`)**:
  - Resolved missing card in Home Assistant's Visual Card Picker (searching for `"ave"`) and `Custom element doesn't exist` dashboard warnings.
  - Integration setup (`async_setup_entry`) now invokes `_async_register_card(hass)` directly to register `/ave_video44_frontend/ave-video44-card.js?v=1.1.2` as a JavaScript module (`res_type: "module"`) inside Home Assistant's Lovelace Storage resource registry (`lovelace.resources`), guaranteeing reliable loading across dashboard reloads and mobile app sessions.
- **Idempotent Frontend Custom Element & Visual Card Registration**:
  - Added guards with `customElements.get("ave-video44-card")` and duplicate checks on `window.customCards` array in `ave-video44-card.js` to ensure clean, error-free reloads without browser console warnings.

### 🇮🇹 Italiano

- **Risolto Errore Lovelace Custom Element (`Custom element doesn't exist: ave-video44-card`)**:
  - Risolta la mancata visualizzazione della card nel selettore visuale delle schede (cercando `"ave"`) e l'errore `Custom element doesn't exist` nelle dashboard Lovelace.
  - L'avvio dell'integrazione (`async_setup_entry`) richiama ora direttamente `_async_register_card(hass)` registrando programmaticamente l'URL `/ave_video44_frontend/ave-video44-card.js?v=1.1.2` come modulo JavaScript (`res_type: "module"`) nel registro risorse Lovelace (`lovelace.resources`), garantendo il caricamento immediato anche su app Companion e riavvii.
- **Registrazione Idempotente dell'Elemento e della Card Visuale**:
  - Introdotti controlli di protezione con `customElements.get("ave-video44-card")` e verifica duplicati su `window.customCards` in `ave-video44-card.js` per prevenire errori di doppia definizione e warning nella console del browser.

## v1.1.1 — 2026-10-25

### 🇬🇧 English

- **Fixed RTSP Connection Refused on 2-Wire Cloud Indoor Monitors (`TS-SMART`)**:
  - Resolved `Error opening stream (Connection refused, rtsp://127.0.0.1:554/live/sub)` on 2-wire bus outdoor doorstations when connected via cloud indoor monitors.
  - In 2-wire installations, outdoor station cameras are physically powered down and inactive during idle states. `camera.py` now returns `None` from `get_rtsp_url()` and `stream_source()` when idle, preventing Home Assistant stream workers from repeatedly spamming connection attempts to inactive local endpoints.
  - Dynamically enables `CameraEntityFeature.STREAM` only when an active RTSP/RTSPS stream URL is actually available.
- **Added Cloud Video Monitoring Endpoints (`core/api.py`)**:
  - Implemented `get_monitoring_list()` and `control_monitoring()` cloud REST API endpoints matching the AVE/GVS cloud protocol, allowing on-demand activation of video streams.
- **Added Offline Device Registry Fallback in Coordinator (`coordinator.py`)**:
  - Added graceful fallback handling in `DataUpdateCoordinator` so device entities remain properly initialized in the Home Assistant registry even if cloud authentication or devices are temporarily unreachable during initial startup.

### 🇮🇹 Italiano

- **Risolto Errore di Connessione RTSP Rifiutata sui Monitor Cloud a 2 Fili (`TS-SMART`)**:
  - Risolto l'errore `Error opening stream (Connection refused, rtsp://127.0.0.1:554/live/sub)` che si verificava con posti esterni su bus 2 fili connessi tramite monitor interno cloud.
  - Negli impianti a 2 fili le telecamere dei posti esterni sono fisicamente spente e disalimentate quando a riposo. L'entità `camera.py` restituisce ora `None` da `get_rtsp_url()` e `stream_source()` in stato di idle, impedendo ai worker di Home Assistant di effettuare tentativi continui di connessione su endpoint locali non raggiungibili.
  - Abilitazione dinamica di `CameraEntityFeature.STREAM` solo ed esclusivamente quando è disponibile un URL di streaming RTSP/RTSPS attivo.
- **Aggiunti Endpoint Cloud di Monitoraggio Video (`core/api.py`)**:
  - Implementati gli endpoint REST cloud `get_monitoring_list()` e `control_monitoring()` conformi al protocollo AVE/GVS, consentendo l'attivazione video su richiesta dal cloud.
- **Aggiunto Fallback Offline nel Registro Dispositivi del Coordinator (`coordinator.py`)**:
  - Gestione resiliente dello stato offline nel `DataUpdateCoordinator`: le entità e i dispositivi rimangono registrati e coerenti nel registro di Home Assistant anche in caso di disconnessione temporanea o mancata risposta cloud durante l'avvio.

## v1.1.0 — 2026-10-25

### 🇬🇧 English

- **Disabled Duplicate Unlock Button Entities (`Apriporta Pedonale` / `Apriporta Carraio`) by Default**:
  - The instantaneous pulse unlock buttons (`button.apriporta_pedonale`, `button.apriporta_carraio`) are now disabled by default in the Home Assistant Entity Registry (`_attr_entity_registry_enabled_default = False`) to prevent UI clutter and confusion.
  - The dedicated lock entities (`lock.serratura_pedonale`, `lock.cancello_carraio`) provide state feedback and pulse timing. Existing installations are automatically migrated on integration startup without breaking user configurations.
- **Guided Intercom Phonebook Wizard in Integration Options (`OptionsFlow`)**:
  - Replaced error-prone raw comma-separated string formatting with an intuitive step-by-step wizard in **Settings -> Devices & services -> AVE Video V44 -> Configure**:
    - **Add/Edit Intercom Contact**: Input friendly Room Name (e.g. `"Taverna"`) and Hardware Extension/IP/SIP Address (e.g. `"0102"` or `"192.168.88.52"`).
    - **Remove Intercom Contact**: Simple single-click dropdown selection to delete obsolete contacts.
    - **General Settings**: Adjust relay unlock pulse duration (seconds) and preferred video stream (sub-stream vs main-stream).
  - Clean `"Nessun interfono configurato"` default fallback option displayed on `select.destinazione_interfono` when the address book is empty, eliminating the confusing `unknown` state.
- **Zero-YAML Lovelace Card Auto-Registration & Visual Editor**:
  - Automatic frontend resource injection via `add_extra_js_url` with `?v=1.1.0` cache-busting: no manual YAML configuration or manual Lovelace resource registration required.
  - Dynamic entity auto-discovery (`getStubConfig(hass)` and `_autoResolveEntities`): automatically detects camera, locks, and sensors from registered `ave_video44` devices in Home Assistant.
  - Built-in visual card editor (`AveVideo44CardEditor` / `ave-video44-card-editor`) with sanitized DOM property manipulation to guard against XSS.

### 🇮🇹 Italiano

- **Disabilitazione Pulsanti Sblocco Duplicati (`Apriporta Pedonale` / `Apriporta Carraio`) per Impostazione Predefinita**:
  - I pulsanti di apertura impulsiva (`button.apriporta_pedonale`, `button.apriporta_carraio`) sono ora disabilitati per impostazione predefinita nel Registro Entità (`_attr_entity_registry_enabled_default = False`) per evitare duplicazioni visive nella scheda Controlli.
  - Le entità serratura dedicate (`lock.serratura_pedonale`, `lock.cancello_carraio`) gestiscono lo sblocco e il feedback visivo. Le installazioni esistenti vengono migrate automaticamente all'avvio senza alterare le configurazioni personalizzate.
- **Wizard Guidato per la Rubrica Interfoni nelle Opzioni (`OptionsFlow`)**:
  - Sostituita la precedente configurazione a stringa manuale con una procedura guidata passo-passo in **Impostazioni -> Dispositivi e servizi -> AVE Video V44 -> Configura**:
    - **Aggiungi/Modifica contatto interfono**: Inserimento guidato del Nome Locale (es. `"Taverna"`) e Codice/Indirizzo Stanza o IP/SIP (es. `"0102"` o `"192.168.88.52"`).
    - **Rimuovi contatto interfono**: Selezione rapida da menu a tendina per eliminare contatti obsoleti.
    - **Impostazioni generali**: Configurazione della durata impulso relè e del flusso video preferito.
  - Opzione predefinita pulita `"Nessun interfono configurato"` su `select.destinazione_interfono` quando la rubrica è vuota, eliminando lo stato `unknown`.
- **Auto-Registrazione Zero-YAML della Card Lovelace ed Editor Visuale**:
  - Iniezione automatica della risorsa frontend via `add_extra_js_url` con cache-busting `?v=1.1.0`: la card è immediatamente disponibile in **Aggiungi scheda** senza modifiche manuali a `configuration.yaml` o alle risorse Lovelace.
  - Auto-discovery dinamico dei dispositivi ed entità (`getStubConfig(hass)` e `_autoResolveEntities`): configurazione istantanea con rilevamento automatico di telecamera, serrature e sensori associati.
  - Editor visuale interattivo (`AveVideo44CardEditor` / `ave-video44-card-editor`) conforme agli standard di sicurezza DOM per prevenire vulnerabilità XSS.

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
