# AVE Video V44 Home Assistant Integration (`ave_video44`)

[![HACS Custom Component](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/default)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue.svg)](https://www.home-assistant.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Integrazione Home Assistant per videocitofoni AVE Video V44 (dispositivi serie VI2F-PIT7WF, TS-SMART e compatibili protocollo GVS). Supporta video streaming live H.264/RTSP, sblocco serrature pedonali e carraie, gestione eventi di chiamata in arrivo, interfono bidirezionale multi-appartamento (HOUSETOHOUSE), card Lovelace integrata con audio full-duplex WebAudio (cancellazione eco e ricampionamento 8kHz PCM16) e Blueprint per notifiche Companion App con deep-link.

Home Assistant custom integration for AVE Video V44 video intercom systems (VI2F-PIT7WF, TS-SMART, and GVS-compatible units). Features live H.264/RTSP streaming, dual-lock control, incoming call events, inter-apartment intercom (HOUSETOHOUSE), a bundled Lovelace card with full-duplex WebAudio (hardware echo cancellation, 8kHz PCM16 resampling), and automated Companion App notification blueprints with interactive deep-linking.

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

- Video Streaming RTSP: visualizzazione continua a 25-30 fps H.264 live del posto esterno con compatibilita WebRTC e go2rtc.
- Controllo Serrature: apertura impulsiva di cancelletto pedonale (Lock ID 1) e cancello carraio (Lock ID 2).
- Audio Bidirezionale Full-Duplex: conversazione vocale fluida direttamente dall'app Home Assistant Companion o dal browser via WebSocket, senza necessita di app terze.
- Ricampionamento Audio 8kHz: la card converte automaticamente i flussi microfonici (44.1kHz o 48kHz) in PCM16 mono a 8000 Hz, interfacciandosi nativamente con i codec G.711a (PCMA) del citofono.
- Eventi di Chiamata: tracciamento in tempo reale tramite binary_sensor e piattaforma event con device_class doorbell.
- Rubrica Interni: selezione dell'interno desiderato (es. Piano Terra, Primo Piano) e avvio chiamata SIP HOUSETOHOUSE.
- Blueprint Notifiche: notifica push ad alta priorita sullo smartphone con fermo immagine del visitatore e pulsanti rapidi ("Rispondi", "Rifiuta", "Apri Cancello").

### Entita Supportate

| Piattaforma | Entita | Descrizione |
| :--- | :--- | :--- |
| `camera` | `camera.posto_esterno_ingresso` | Stream video live RTSP e fermo immagine snapshot |
| `lock` | `lock.posto_esterno_cancelletto_pedonale` | Serratura cancelletto pedonale (Lock 1) con auto-ripristino |
| `lock` | `lock.posto_esterno_cancello_carraio` | Serratura cancello carrabile (Lock 2) |
| `button` | `button.apri_cancelletto` | Pulsante rapido di apertura pedonale |
| `button` | `button.apri_cancello_carraio` | Pulsante rapido di apertura carrabile |
| `event` | `event.posto_esterno_chiamata` | Evento campanello (doorbell_press, call_answered, call_missed) |
| `binary_sensor` | `binary_sensor.posto_esterno_chiamata_in_corso` | Attivo durante lo squillo o la conversazione |
| `sensor` | `sensor.posto_esterno_stato_chiamata` | Stato citofono (idle, ringing, talking, monitoring) |
| `select` | `select.rubrica_interni` | Elenco contatti configurati per chiamate interfono |

### Installazione tramite HACS

1. Assicurarsi di aver installato HACS (Home Assistant Community Store).
2. Andare su HACS -> Integrazioni -> Menu tre puntini in alto a destra -> Repository personalizzati.
3. Incollare l'URL del repository: `https://github.com/federico/Ave-video44-HA` (o il percorso del proprio fork).
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

Nelle Opzioni dell'integrazione (Impostazioni -> Dispositivi e Servizi -> AVE Video V44 -> Configura) e possibile definire la Rubrica Interni nel formato `codice=etichetta` separati da virgola:

```text
1-1-101=Piano Terra, 1-1-102=Primo Piano, 1-1-103=Appartamento Ovest
```

Questo popola dinamicamente il selettore `select.rubrica_interni` e abilita il servizio `ave_video44.call_intercom` per avviare comunicazioni voce tra alloggi.

### Card Lovelace (ave-video44-card)

La card personalizzata e inclusa e registrata automaticamente:

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
- Design scuro tecnico ad alto contrasto conforme alle linee guida WCAG AA (rapporto di contrasto superiore a 4.5:1).
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

- Live RTSP Video Streaming: 25-30 fps H.264 stream from the outdoor station, fully compatible with WebRTC and go2rtc.
- Dual-Lock Actuation: pulse activation for pedestrian gate (Lock ID 1) and driveway sliding gate (Lock ID 2).
- Full-Duplex Bidirectional Audio: live voice call through Home Assistant Companion app or web browser over authenticated WebSocket, without proprietary third-party apps.
- 8kHz PCM16 Resampling Engine: converts browser audio (44.1kHz or 48kHz) to 8000 Hz mono PCM16, matching the intercom G.711a A-law codec.
- Doorbell Call Lifecycle: real-time updates via binary_sensor and event platforms with doorbell device class.
- Inter-Apartment Intercom Directory: select an indoor station from the address book and trigger HOUSETOHOUSE SIP calls.
- Companion Notification Blueprint: high-priority push notifications with visitor snapshot, interactive action buttons ("Rispondi", "Rifiuta", "Apri Cancello"), and instant deep-link answering.

### Supported Entities

| Platform | Entity ID | Description |
| :--- | :--- | :--- |
| `camera` | `camera.posto_esterno_ingresso` | Live RTSP stream and snapshot preview |
| `lock` | `lock.posto_esterno_cancelletto_pedonale` | Pedestrian lock (Lock 1) with auto-relock |
| `lock` | `lock.posto_esterno_cancello_carraio` | Driveway gate lock (Lock 2) |
| `button` | `button.apri_cancelletto` | Instant pedestrian unlock trigger |
| `button` | `button.apri_cancello_carraio` | Instant driveway gate trigger |
| `event` | `event.posto_esterno_chiamata` | Doorbell press and call termination events |
| `binary_sensor` | `binary_sensor.posto_esterno_chiamata_in_corso` | On during ringing or active conversation |
| `sensor` | `sensor.posto_esterno_stato_chiamata` | Intercom call state (idle, ringing, talking, monitoring) |
| `select` | `select.rubrica_interni` | Configured intercom address book entries |

### Installation via HACS

1. Make sure HACS is installed on your Home Assistant instance.
2. In HACS, navigate to Integrations -> three dots menu (top right) -> Custom repositories.
3. Add repository URL: `https://github.com/federico/Ave-video44-HA`.
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

In integration options (Settings -> Devices & Services -> AVE Video V44 -> Configure), specify intercom extensions using comma-separated `code=label` pairs:

```text
1-1-101=Ground Floor, 1-1-102=First Floor, 1-1-103=West Wing
```

This populates `select.rubrica_interni` and empowers `ave_video44.call_intercom` to initiate calls between monitors.

### Lovelace Card (ave-video44-card)

The bundled custom element card is served directly by the integration:

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
- Dark technical utility theme compliant with WCAG AA contrast standards (> 4.5:1 ratio).
- State memoization to preserve active calls and audio streaming across Home Assistant updates.
- Full-duplex WebAudio with echo cancellation, automatic gain control, and 8kHz PCM16 resampling.
- Accessible ARIA modal semantics with Escape key dismissal support.
- Built-in error handling and zero decorative emoji clutter.

### Notification Blueprint

Included at `custom_components/ave_video44/blueprints/automation/incoming_call_notification.yaml`:
- Dispatches critical Companion App notifications when the doorbell rings.
- Presents actionable buttons: Answer, Reject, Unlock Gate.
- Interactive deep-link: opens `/lovelace/citofono?ave_call=answer&device_id=...` to automatically open the live call feed with hands-free audio enabled.
- Optional multi-room TTS voice announcements on selected media player devices.
