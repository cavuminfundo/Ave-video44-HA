<p align="center">
  <img src="https://raw.githubusercontent.com/cavuminfundo/Ave-video44-HA/main/custom_components/ave_video44/brand/logo.png" alt="AVE Video V44" width="240" />
</p>

# AVE Video V44 Home Assistant Integration (`ave_video44`)

[![GitHub Release](https://img.shields.io/github/v/release/cavuminfundo/Ave-video44-HA?color=blue)](https://github.com/cavuminfundo/Ave-video44-HA/releases)
[![Validate](https://github.com/cavuminfundo/Ave-video44-HA/actions/workflows/validate.yml/badge.svg)](https://github.com/cavuminfundo/Ave-video44-HA/actions/workflows/validate.yml)
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=cavuminfundo&repository=Ave-video44-HA&category=integration)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue.svg)](https://www.home-assistant.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> [!CAUTION]
> **[IT] PROGETTO IN FASE DI SVILUPPO ATTIVO — UTILIZZO A PROPRIO RISCHIO E PERICOLO**
> Questa integrazione è un progetto indipendente e non ufficiale (non affiliato né supportato da AVE S.p.A.), attualmente in fase di **sviluppo attivo e sperimentazione**. Poiché interagisce con sistemi di controllo accessi fisici (serrature pedonali, cancelli carrai e postazioni videocitofoniche), l'installazione e l'utilizzo avvengono **esclusivamente a proprio rischio e pericolo**. Gli autori declinano ogni responsabilità per aperture involontarie, malfunzionamenti, danni hardware o interruzioni del servizio.
>
> **[EN] ACTIVE DEVELOPMENT — USE AT YOUR OWN RISK**
> This integration is an independent, unofficial community project (not affiliated with or endorsed by AVE S.p.A.) and is currently under **active development**. Because it interacts with physical access control hardware (pedestrian locks, driveway gates, and video intercom stations), you use it **entirely at your own risk**. The authors assume no liability for unintended unlocks, malfunctions, hardware damage, or service disruptions.

Integrazione Home Assistant per videocitofoni AVE Video V44 (dispositivi serie VI2F-PIT7WF, TS-SMART e compatibili protocollo GVS). Supporta video streaming live H.264/RTSP, sblocco serrature pedonali e carraie, gestione eventi di chiamata in arrivo, interfono bidirezionale multi-appartamento (HOUSETOHOUSE), card Lovelace integrata con audio full-duplex WebAudio (cancellazione eco e ricampionamento 8kHz PCM16) e Blueprint per notifiche Companion App con deep-link.

Home Assistant custom integration for AVE Video V44 video intercom systems (VI2F-PIT7WF, TS-SMART, and GVS-compatible units). Features live H.264/RTSP streaming, dual-lock control, incoming call events, inter-apartment intercom (HOUSETOHOUSE), a bundled Lovelace card with full-duplex WebAudio (hardware echo cancellation, 8kHz PCM16 resampling), and automated Companion App notification blueprints with interactive deep-linking.

---

## Repository Documentation Index

- [.agents/AGENTS.md](.agents/AGENTS.md)
- [.agents/memory/lessons.md](.agents/memory/lessons.md)
- [docs/architecture.md](docs/architecture.md)
- [docs/roadmap.md](docs/roadmap.md)
- [docs/code-implementation.md](docs/code-implementation.md)
- [CHANGELOG.md](CHANGELOG.md)

---

## Indice / Table of Contents

- [Italiano](#italiano)
  - [Caratteristiche Principali](#caratteristiche-principali)
  - [Entita Supportate](#entita-supportate)
  - [Installazione tramite HACS](#installazione-tramite-hacs)
  - [Configurazione](#configurazione)
  - [Rubrica Interni (HOUSETOHOUSE)](#rubrica-interni-housetohouse)
  - [Card Lovelace (ave-video44-card)](#card-lovelace-ave-video44-card)
  - [Blueprint Notifiche Smartphone](#blueprint-notifiche-smartphone)
- [English](#english)
  - [Key Features](#key-features)
  - [Supported Entities](#supported-entities)
  - [Installation via HACS](#installation-via-hacs)
  - [Configuration](#configuration)
  - [Intercom Address Book (HOUSETOHOUSE)](#intercom-address-book-housetohouse)
  - [Lovelace Card (ave-video44-card)](#lovelace-card-ave-video44-card)
  - [Notification Blueprint](#notification-blueprint)

---

## Italiano

### Caratteristiche Principali

- Video Streaming RTSP / RTSPS / Cloud SIP: visualizzazione live H.264/RTSPS (porta 8322) e Cloud SIP/SRTP (porta 5060) del posto esterno con proxy FFmpeg integrato per snapshot e flussi live, pienamente compatibile con WebRTC e go2rtc.
- Risveglio Telecamera On-Demand: accensione e visualizzazione su richiesta della telecamera dei posti esterni a 2 fili (normalmente a riposo per risparmio energetico) tramite pulsante dedicato o pulsante "Attiva Video" nella card.
- Controllo Serrature: apertura impulsiva di cancelletto pedonale (Lock ID 1) e cancello carraio (Lock ID 2).
- Audio Bidirezionale Full-Duplex: conversazione vocale fluida direttamente dall'app Home Assistant Companion o dal browser via WebSocket, senza necessita di app terze.
- Ricampionamento Audio 8kHz: la card converte automaticamente i flussi microfonici (44.1kHz o 48kHz) in PCM16 mono a 8000 Hz, interfacciandosi nativamente con i codec G.711a (PCMA) del citofono.
- Eventi di Chiamata: tracciamento in tempo reale tramite binary_sensor e piattaforma event con device_class doorbell.
- Rubrica Interni ed Auto-Discovery: rilevamento automatico a 1 clic degli interni e avvio chiamata SIP HOUSETOHOUSE.
- Card Lovelace Bubble Card: interfaccia moderna a pillola con pulsanti ad icone a bolla, titolo personalizzabile e layout responsive desktop/mobile.
- Dashboard Laterale Opzionale: plancia dedicata "Videocitofono" attivabile o disattivabile nella barra laterale dalle impostazioni dell'integrazione.
- Blueprint Notifiche: notifica push ad alta priorita sullo smartphone con fermo immagine del visitatore e pulsanti rapidi ("Rispondi", "Rifiuta", "Apri Cancello").

### Entita Supportate

| Piattaforma | Entita | Descrizione |
| :--- | :--- | :--- |
| `camera` | `camera.posto_esterno_ingresso` | Stream video live RTSP e fermo immagine snapshot |
| `lock` | `lock.posto_esterno_cancelletto_pedonale` | Serratura cancelletto pedonale (Lock 1) con auto-ripristino |
| `lock` | `lock.posto_esterno_cancello_carraio` | Serratura cancello carrabile (Lock 2) |
| `button` | `button.attiva_telecamera` | Risveglio ed accensione telecamera posto esterno su richiesta (abilitato per impostazione predefinita) |
| `button` | `button.apri_cancelletto` | Pulsante rapido sblocco pedonale (disabilitato per impostazione predefinita in favore dell'entita lock) |
| `button` | `button.apri_cancello_carraio` | Pulsante rapido sblocco carraio (disabilitato per impostazione predefinita in favore dell'entita lock) |
| `event` | `event.posto_esterno_chiamata` | Evento campanello (doorbell_press, call_answered, call_missed) |
| `binary_sensor` | `binary_sensor.posto_esterno_chiamata_in_corso` | Attivo durante lo squillo o la conversazione |
| `sensor` | `sensor.posto_esterno_stato_chiamata` | Stato citofono (idle, ringing, talking, monitoring) |
| `select` | `select.rubrica_interni` | Elenco contatti configurati per chiamate interfono |

Nota: Il pulsante di risveglio telecamera (`button.attiva_telecamera`) e abilitato per impostazione predefinita per consentire l'accensione manuale dei posti esterni a 2 fili. I pulsanti rapidi di apertura (`button.apri_cancelletto`, `button.apri_cancello_carraio`) sono disabilitati per impostazione predefinita nel Registro Entita per evitare duplicazioni visive nella dashboard Controlli con le entita `lock` dedicate, che gestiscono anche stato e temporizzazione del relè. Possono essere riabilitati in qualsiasi momento dal Registro Entita se desiderati per scorciatoie o automazioni.

### Installazione tramite HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=cavuminfundo&repository=Ave-video44-HA&category=integration)

1. Assicurarsi di aver installato HACS (Home Assistant Community Store).
2. Andare su HACS -> Integrazioni -> Menu tre puntini in alto a destra -> Repository personalizzati.
3. Incollare l'URL del repository: `https://github.com/cavuminfundo/Ave-video44-HA` (o il percorso del proprio fork).
4. Selezionare la categoria "Integrazione" e confermare.
5. Cercare "AVE Video V44", cliccare su Scarica e riavviare Home Assistant.

### Configurazione

1. In Home Assistant andare su Impostazioni -> Dispositivi e Servizi -> Aggiungi Integrazione.
2. Cercare "AVE Video V44".
3. Metodo di autenticazione:
   - Password: inserire account email e password registrata nell'applicazione AVE / GVS Cloud.
   - Codice OTP: richiedere un codice temporaneo inviato via email e confermare con il codice a 6 cifre.
4. L'integrazione scoprira automaticamente i posti esterni e i monitor interni associati all'impianto.

### Rubrica Interni (HOUSETOHOUSE)

Nelle Opzioni dell'integrazione (**Impostazioni -> Dispositivi e Servizi -> AVE Video V44 -> Configura**) e disponibile una procedura guidata interattiva passo-passo per gestire la rubrica:

1. Selezionare **Scopri automaticamente interni e posti esterni (Auto-Discovery)** per scansionare l'impianto e importare tutti i monitor ed estensioni rilevati in un solo clic.
2. Selezionare **Aggiungi o modifica contatto**:
   - Inserire il nome della stanza o locale (es. `Taverna`, `Studio`, `Primo Piano`).
   - Inserire il codice interno GVS/AVE (es. `0102` o `1-1-102`) oppure l'indirizzo IP/SIP.
3. Per eliminare contatti non piu utilizzati, selezionare **Rimuovi contatto** e scegliere la voce desiderata dal menu a tendina.
4. Per regolare la durata dell'impulso relè, il flusso video preferito o la visibilita della dashboard nella barra laterale, selezionare **Impostazioni generali**.

Questo popola dinamicamente il selettore `select.rubrica_interni` (con auto-seeding automatico all'avvio e opzione predefinita `Nessun interfono configurato` quando la rubrica e vuota) e abilita il servizio `ave_video44.call_intercom` per avviare comunicazioni voce tra alloggi.

### Card Lovelace (ave-video44-card)

La card personalizzata viene registrata automaticamente all'avvio di Home Assistant come modulo JavaScript nel registro risorse Lovelace tramite il percorso anti-cache `/ave_video44_card/ave-video44-card.js?v=1.2.4`, senza richiedere interventi manuali alle Risorse Lovelace (Zero-YAML).

Per aggiungere la card a qualsiasi plancia tramite editor visuale (Zero-YAML):
1. In qualsiasi dashboard Lovelace, cliccare sul menu in alto a destra (tre puntini) -> **Modifica Plancia**.
2. Cliccare su **Aggiungi scheda** in basso a destra.
3. Cercare e selezionare **AVE Video V44 Card** dall'elenco delle schede disponibili.
4. L'editor visuale (`ave-video44-card-editor`) consente di personalizzare il titolo della scheda e scoprira e colleghera automaticamente la telecamera, il pulsante di accensione, le serrature, il campanello e i sensori del tuo impianto AVE.
5. Cliccare su **Salva**.

In alternativa, per plance gestite via YAML:

```yaml
type: custom:ave-video44-card
title: Videocitofono Ingresso
entity: camera.posto_esterno_ingresso
device_id: doorstation_001
intercom_select: select.rubrica_interni
call_state_sensor: sensor.posto_esterno_stato_chiamata
doorbell_binary_sensor: binary_sensor.posto_esterno_chiamata_in_corso
lock_pedestrian: lock.posto_esterno_cancelletto_pedonale
lock_driveway: lock.posto_esterno_cancello_carraio
```

Caratteristiche della Card:
- Design moderno stile Bubble Card con contenitore a pillola (`border-radius: 28px`) e pulsanti ad icone circolari a bolla.
- Titolo della card personalizzabile via editor visuale o parametro YAML `title`.
- Layout responsive desktop (griglia ad auto-adattamento) e mobile (fino a 780px in modalita pannello).
- Configurazione Zero-YAML con editor visuale integrato ed auto-discovery delle entita dell'impianto.
- Pulsante "Attiva Video" a riposo per risvegliare e visualizzare immediatamente la telecamera dei posti esterni a 2 fili.
- Memoizzazione degli stati per non interrompere lo streaming video o la chiamata in corso durante gli aggiornamenti di Home Assistant.
- Supporto alla scorciatoia tasto Escape per chiudere la chiamata.
- Zero dipendenze da librerie esterne pesanti; uso nativo dei componenti HA.

### Blueprint Notifiche Smartphone

Il template di automazione e incluso in `custom_components/ave_video44/blueprints/automation/incoming_call_notification.yaml`:
- Invia una notifica push istantanea con snapshot del visitatore.
- Inserisce pulsanti di azione rapida ("Rispondi", "Rifiuta", "Apri Cancello").
- Deep-link automatico: toccando la notifica viene aperta la dashboard Lovelace con query parameter `?ave_call=answer&device_id=...`, attivando immediatamente vivavoce e video live.
- Annuncio opzionale TTS su altoparlanti intelligenti e smart display collegati.

---

## English

### Key Features

- Live RTSP / RTSPS / Cloud SIP Video Streaming: 25-30 fps H.264/RTSPS live cloud stream (port 8322) and Cloud SIP/SRTP (port 5060) with FFmpeg snapshot proxy, fully compatible with WebRTC and go2rtc.
- On-Demand Camera Wake: power up and view 2-wire outdoor doorstation cameras on demand (normally powered off when idle to conserve energy) using a dedicated wake button entity or "Attiva Video" card control.
- Dual-Lock Actuation: pulse activation for pedestrian gate (Lock ID 1) and driveway sliding gate (Lock ID 2).
- Full-Duplex Bidirectional Audio: live voice call through Home Assistant Companion app or web browser over authenticated WebSocket, without proprietary third-party apps.
- Ricampionamento Audio 8kHz: converts browser audio (44.1kHz or 48kHz) to 8000 Hz mono PCM16, matching the intercom G.711a A-law codec.
- Doorbell Call Lifecycle: real-time updates via binary_sensor and event platforms with doorbell device class.
- Inter-Apartment Intercom Directory & 1-Click Auto-Discovery: instant scan of indoor stations and doorstations, triggering HOUSETOHOUSE SIP calls.
- Bubble Card Lovelace UI: modern pill container styling, circular icon bubbles, customizable title, and responsive desktop/mobile layout.
- Optional Sidebar Dashboard: dedicated "Videocitofono" panel dashboard toggleable via Integration Options.
- Companion Notification Blueprint: high-priority push notifications with visitor snapshot, interactive action buttons ("Rispondi", "Rifiuta", "Apri Cancello"), and instant deep-link answering.

### Supported Entities

| Platform | Entity ID | Description |
| :--- | :--- | :--- |
| `camera` | `camera.posto_esterno_ingresso` | Live RTSP stream and snapshot preview |
| `lock` | `lock.posto_esterno_cancelletto_pedonale` | Pedestrian lock (Lock 1) with auto-relock |
| `lock` | `lock.posto_esterno_cancello_carraio` | Driveway gate lock (Lock 2) |
| `button` | `button.attiva_telecamera` | On-demand camera wake trigger for 2-wire doorstations (enabled by default) |
| `button` | `button.apri_cancelletto` | Instant pedestrian unlock trigger (disabled by default in favor of lock entity) |
| `button` | `button.apri_cancello_carraio` | Instant driveway gate trigger (disabled by default in favor of lock entity) |
| `event` | `event.posto_esterno_chiamata` | Doorbell press and call termination events |
| `binary_sensor` | `binary_sensor.posto_esterno_chiamata_in_corso` | On during ringing or active conversation |
| `sensor` | `sensor.posto_esterno_stato_chiamata` | Intercom call state (idle, ringing, talking, monitoring) |
| `select` | `select.rubrica_interni` | Configured intercom address book entries |

Note: The camera wake button (`button.attiva_telecamera`) is enabled by default to allow manual wake-up of 2-wire bus outdoor stations. Instant unlock buttons (`button.apri_cancelletto`, `button.apri_cancello_carraio`) are disabled by default in the Entity Registry to prevent visual duplication on the Controls dashboard alongside dedicated `lock` entities, which also reflect relay state and timing. They can be re-enabled at any time in the Entity Registry for quick shortcuts or automations.

### Installation via HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=cavuminfundo&repository=Ave-video44-HA&category=integration)

1. Make sure HACS is installed on your Home Assistant instance.
2. In HACS, navigate to Integrations -> three dots menu (top right) -> Custom repositories.
3. Add repository URL: `https://github.com/cavuminfundo/Ave-video44-HA`.
4. Select category "Integration" and confirm.
5. Find "AVE Video V44", click Download, and restart Home Assistant.

### Configuration

1. In Home Assistant, open Settings -> Devices & Services -> Add Integration.
2. Search for "AVE Video V44".
3. Choose authentication:
   - Password: provide registered cloud account credentials.
   - OTP Code: request a one-time code by email and submit the 6-digit confirmation.
4. Outdoor stations and indoor monitors will be detected and registered automatically.

### Intercom Address Book (HOUSETOHOUSE)

In integration options (**Settings -> Devices & Services -> AVE Video V44 -> Configure**), an interactive step-by-step wizard is available to manage the address book:

1. Select **Auto-discover intercom extensions** to scan your installation and import all discovered monitors, extensions, and relays in a single click.
2. Select **Add or edit contact**:
   - Enter a friendly room or station name (e.g., `Downstairs`, `Study`, `Upper Floor`).
   - Enter the GVS/AVE intercom extension code (e.g., `0102` or `1-1-102`) or IP/SIP address.
3. To remove obsolete entries, select **Remove contact** and choose the entry from the dropdown menu.
4. To adjust relay pulse duration, preferred video stream profile, or toggle sidebar dashboard visibility, select **General settings**.

This dynamically populates `select.rubrica_interni` (with automatic startup seeding and default fallback `Nessun interfono configurato` when no intercom contacts are configured) and empowers `ave_video44.call_intercom` to initiate calls between indoor monitors.

### Lovelace Card (ave-video44-card)

The bundled custom card is registered automatically on Home Assistant startup inside the Lovelace storage resource registry via the dedicated cache-bypass path `/ave_video44_card/ave-video44-card.js?v=1.2.4` (res_type: "module"), eliminating stale cache issues in mobile apps (Zero-YAML).

To add the card to any dashboard using the visual UI editor:
1. In any Lovelace dashboard, click the top-right menu (three dots) -> **Edit Dashboard**.
2. Click **Add Card** at the bottom right.
3. Search for and select **AVE Video V44 Card** from the card picker.
4. The visual editor (`ave-video44-card-editor`) allows customizing the card title and will automatically discover and populate your outdoor camera, locks, doorbell, and intercom entities.
5. Click **Save**.

Alternatively, for YAML-managed dashboards:

```yaml
type: custom:ave-video44-card
title: Entrance Doorbell
entity: camera.posto_esterno_ingresso
device_id: doorstation_001
intercom_select: select.rubrica_interni
call_state_sensor: sensor.posto_esterno_stato_chiamata
doorbell_binary_sensor: binary_sensor.posto_esterno_chiamata_in_corso
lock_pedestrian: lock.posto_esterno_cancelletto_pedonale
lock_driveway: lock.posto_esterno_cancello_carraio
```

Card Highlights:
- Modern Bubble Card design with pill container (border-radius: 28px) and circular icon bubbles.
- Customizable card title via visual editor or YAML title configuration.
- Responsive multi-device layout: desktop auto-fit grid and mobile panel view (max-width: 780px).
- Zero-YAML automatic registration with integrated visual editor and entity auto-discovery.
- Idle "Attiva Video" monitor button to wake and view 2-wire doorstation cameras instantly.
- State memoization to preserve active calls and audio streaming across Home Assistant updates.
- Full-duplex WebAudio with echo cancellation, automatic gain control, and 8kHz PCM16 resampling.
- Accessible ARIA modal semantics with Escape key dismissal support.
- Built-in error handling, zero external heavyweight dependencies, and zero decorative emoji clutter.

### Notification Blueprint

Included at `custom_components/ave_video44/blueprints/automation/incoming_call_notification.yaml`:
- Dispatches critical Companion App notifications when the doorbell rings.
- Presents actionable buttons: Answer, Reject, Unlock Gate.
- Interactive deep-link: opens `/lovelace/citofono?ave_call=answer&device_id=...` to automatically open the live call feed with hands-free audio enabled.
- Optional multi-room TTS voice announcements on selected media player devices.
