# Specifiche Architetturali: Audio Bidirezionale AVE Video V44

- **Document ID**: `SPEC-AVE-VIDEO44-AUDIO-002`
- **Data**: 2026-10-26
- **Autore**: Antigravity
- **Stato**: Approvato in Brainstorming
- **Target Platform**: Home Assistant Core >= 2024.1.0
- **Repository Path**: `/home/federico/Ave-video44-HA`
- **File di Riferimento**:
  - Backend: `custom_components/ave_video44/core/sip_session.py`
  - Backend API: `custom_components/ave_video44/websocket_api.py`
  - Coordinator: `custom_components/ave_video44/coordinator.py`
  - Frontend: `custom_components/ave_video44/frontend/ave-video44-card.js`

---

## 1. Contesto e Problema

L'integrazione Home Assistant `ave_video44` supporta la gestione dello streaming video e degli eventi del sistema videocitofonico AVE Video V44 (dispositivi AVE / GVS serie TS-SMART e posti esterni a 2 fili / IP). Lo streaming video H.264 viene decrittato e transcodificato tramite un sottoprocesso locale FFmpeg alimentato dal relay di pacchetti SRTP ricevuti dal cloud/proxy GVS, ed è visualizzato tramite MJPEG pipeline sulla card Lovelace interattiva `ave-video44-card.js`.

Tuttavia, l'audio bidirezionale presenta deficit strutturali che ne impediscono l'utilizzo pratico:

1. **Scarto dei Pacchetti Audio nel Backend**: All'interno del loop di relay UDP di `CloudSipMediaSession` in `sip_session.py`, i pacchetti SRTP audio in arrivo sulla porta socket locale `_audio_sock` vengono contati ma scartati senza inoltro a FFmpeg né decodifica, rendendo la sessione completamente priva di audio in ricezione (RX muto).
2. **Crash e Blocco Card su PC Desktop Privi di Microfono**: La funzione `_answer()` nella card Lovelace richiama obbligatoriamente `navigator.mediaDevices.getUserMedia()`. Su workstation fisse, mini-PC o postazioni prive di microfono fisico, la chiamata genera un'eccezione non recuperabile (`NotFoundError` / `NotAllowedError`), che interrompe l'esecuzione e impedisce l'avvio della sessione multimediale, precludendo all'utente anche il semplice ascolto dell'audio proveniente dal posto esterno.
3. **Ambiente di Esecuzione Mobile Primario**: Lo scenario operativo principale prevede l'uso dell'applicazione ufficiale **Home Assistant Companion App su Android**, con traffico veicolato tramite tunnel crittografato **Tailscale VPN su HTTPS**. La WebView Android impone vincoli stringenti di compatibilità JavaScript, gestione delle Autoplay Policy di WebAudio, mitigazione dell'eco acustico e tolleranza al jitter tipico delle reti mobili.

Il presente documento definisce l'architettura tecnica per implementare il flusso audio full-duplex, garantendo separazione tra ascolto passivo e trasmissione vocale, tolleranza ai dispositivi senza microfono e conformità agli standard di Home Assistant.

---

## 2. Obiettivi e Non-Obiettivi

### 2.1. Obiettivi
- **Fase 1 (Audio RX - Ascolto)**: Ricezione, decodifica a bassa latenza e riproduzione dell'audio catturato dal microfono del posto esterno su qualsiasi client Home Assistant (desktop o mobile), senza richiedere la disponibilità o l'autorizzazione di un microfono locale.
- **Fase 2 (Audio TX - Parlato)**: Acquisizione della voce dal microfono del client (se presente e autorizzato), ricampionamento standard a 8000 Hz PCM16 mono, trasmissione a pacchetti da 20 ms tramite WebSocket e packetizing SRTP verso il posto esterno.
- **Separazione Rigorosa dei Flussi**: Il flusso video MJPEG, il flusso audio RX, il flusso audio TX e i comandi di apertura serrature/cancelli devono essere completamente disaccoppiati. L'apertura del cancello non deve interrompere l'audio né il video.
- **Supporto Trasparente WebView Android**: Compatibilità completa con i runtime WebView Android legacy e moderni, evitando costrutti sintattici non retrocompatibili.
- **Diagnostica e Telemetria Low-Overhead**: Monitoraggio continuo dei livelli audio (RMS) e delle metriche di rete/frame ogni 5 secondi, senza impatto sulle performance della CPU dell'host.

### 2.2. Non-Obiettivi
- **Nessuna Architettura WebRTC Pesante**: Non verrà introdotto un server ICE/STUN/TURN proprietario all'interno del componente; la trasmissione sfrutterà il relay SRTP e la connessione WebSocket nativa di Home Assistant Core già attiva.
- **Nessuna Modifica al Pipeline Video**: Il canale video H.264 -> MJPEG rimarrà inalterato nella sua catena di decodifica e visualizzazione.
- **Nessuna Alterazione dei Protocolli di Rete Locale GVS**: I pacchetti binari di controllo su porta UDP 8300 rimangono invariati.

---

## 3. Semantica Pulsanti Card Lovelace

La card `ave-video44-card.js` deve presentare comportamenti chiari e prevedibili in funzione dello stato del videocitofono e delle periferiche disponibili sul client.

| Pulsante / Azione | Condizione di Attivazione | Video | Audio RX (Altoparlante) | Audio TX (Microfono) | Azioni di Rete & SIP |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Attiva video** (`_monitor`) | Stato `idle`, click utente | Attivo | **Attivo** (ascolto posto esterno) | **Disattivo** (nessun accesso mic) | Wake camera SIP/MQTT, avvio FFmpeg video + FFmpeg audio RX, iscrizione `ws_audio_subscribe`. |
| **Chiama** (`_callIntercom`) | Stato `idle`, selezione interno | Attivo | **Attivo** | **Attivo** (richiede mic; fallback a RX se negato) | INVITE SIP verso posto esterno o interno, avvio RX e avvio TX via `ws_audio_tx`. |
| **Rispondi** (`_answer`) | Stato `ringing` (chiamata in arrivo) | Attivo | **Attivo** | **Attivo** (richiede mic; fallback a RX se negato) | Invio comando 200 OK / Answer su SIP, avvio full-duplex. |
| **Chiudi** (`_hangup`) | Stato `talking` o `monitoring` | Stop | Stop | Stop | Invio SIP BYE, chiusura WebSocket audio, distruzione `AudioContext`, rilascio tracce microfoniche. |
| **Cancello Pedonale** (`_unlock(1)`) | Qualsiasi stato | Invariato | Invariato | Invariato | Comando INFO SIP o servizio Home Assistant `lock.unlock` (asincrono, non bloccante). |
| **Cancello Carraio** (`_unlock(2)`) | Qualsiasi stato | Invariato | Invariato | Invariato | Comando INFO SIP o servizio Home Assistant `lock.unlock` (asincrono, non bloccante). |

### 3.1. Gestione Graceful dell'Assenza di Microfono
Quando l'utente preme **Chiama** o **Rispondi**:
1. La card tenta di acquisire il microfono tramite `navigator.mediaDevices.getUserMedia`.
2. Se la chiamata fallisce per assenza di periferica (`NotFoundError`), permessi negati (`NotAllowedError`) o contesto non sicuro:
   - La card visualizza una notifica non bloccante: *"Microfono non rilevato: sessione avviata in solo ascolto"*.
   - Il canale Audio RX viene comunque attivato regolarmente insieme al video.
   - Il pulsante Muto nella UI viene disabilitato con label *"Microfono assente"*.
   - La sessione continua senza generare eccezioni fatali.

```
+-------------------------------------------------------------------+
|                        ave-video44-card                           |
+-------------------------------------------------------------------+
|  [ VIDEO STREAM / MJPEG CONTAINER                               ] |
|                                                                   |
|  Stato Chiamata: IN CONVERSAZIONE / MONITORAGGIO                 |
|  Audio Level: [IIIIIIIIII........] -18 dB (RX)                    |
+-------------------------------------------------------------------+
|  [ Pedonale ]      [ Carraio ]      [ Muto ]      [ CHIUDI (Red) ]|
+-------------------------------------------------------------------+
```

---

## 4. Architettura Backend: FFmpeg SRTP / G.711 Relay

L'architettura adotta l'**Approccio A (FFmpeg SRTP/G.711 relay)**, sfruttando la comprovata affidabilità di FFmpeg per gestire la decrittazione SRTP, la decodifica del codec vocale e la conversione a frequenza fissa.

```
                      +-----------------------------+
                      | Posto Esterno / Cloud GVS   |
                      +-----------------------------+
                        |                        ^
       SRTP Inbound     |                        |  SRTP Outbound
    (PCMU/PCMA encrypted|                        | (PCMU/PCMA encrypted)
                        v                        |
               +------------------+     +------------------+
               |  _audio_sock     |     |   _audio_sock    |
               |  (Cloud Media)   |     |   (Cloud Media)  |
               +------------------+     +------------------+
                        |                        ^
            Local UDP   |                        |  SRTP Encrypt /
            Loopback    v                        |  PCM16 to G.711
               +------------------+              |
               |  FFmpeg Audio RX |              |
               |  Subprocess      |              |
               +------------------+              |
                        |                        |
               stdout   | PCM16 Raw              |
               Pipe     | 8000Hz Mono            |
                        v                        |
               +------------------+     +------------------+
               | rx_pcm16_callback|     | send_pcm16_frame |
               +------------------+     +------------------+
                        |                        ^
            WebSocket   | Event                  |  Message
            API         v                        |
               +-------------------------------------------+
               |         Home Assistant websocket_api      |
               +-------------------------------------------+
                        |                        ^
        ws_audio_       |                        |  ws_audio_tx
        subscribe       v                        |  (Base64 PCM16)
               +-------------------------------------------+
               |         Lovelace ave-video44-card         |
               |               (Browser/App)               |
               +-------------------------------------------+
```

### 4.1. Flusso Audio RX (Inbound: Citofono -> Client)

1. **Ricezione Socket SRTP**:
   - `CloudSipMediaSession` apre un socket UDP non bloccante `_audio_sock` associato alla porta audio locale negoziata durante l'INVITE SIP (es. porta allocata dinamicamente o fissa `AUDIO_PORT`).
   - I datagrammi SRTP in arrivo dal citofono contengono payload audio G.711 crittografato (PCMU payload 0 o PCMA payload 8 a seconda del 200 OK SDP del callee).
2. **Relay UDP Locale Verso FFmpeg**:
   - Viene allocata una porta locale loopback `_ffmpeg_audio_port` su `127.0.0.1`.
   - Nel metodo `_udp_relay_loop`, ogni pacchetto ricevuto su `_audio_sock` viene reindirizzato immediatamente:
     ```python
     self._audio_sock.sendto(pkt, ("127.0.0.1", self._ffmpeg_audio_port))
     ```
3. **Generazione Descrittore SDP per FFmpeg Audio**:
   - Viene creato un file temporaneo `/tmp/ave_video44_audio_{device_id}_{hash}.sdp` protetto con permessi `0o600`:
     ```text
     v=0
     o=- 0 0 IN IP4 127.0.0.1
     s=CloudSipAudioSession
     c=IN IP4 127.0.0.1
     t=0 0
     m=audio {ffmpeg_audio_port} RTP/SAVP {audio_payload_type}
     a=rtpmap:{audio_payload_type} {codec_name}/8000
     a=crypto:1 {crypto_suite} inline:{crypto_key}
     ```
   - Dove `codec_name` è `PCMU` per payload `0` o `PCMA` per payload `8`, e `crypto_suite` / `crypto_key` corrispondono a quelli estratti dal 200 OK SDP remoto.
4. **Subprocesso FFmpeg Audio RX**:
   - Il comando invocato per la decodifica audio opera in modalità real-time a latenza minima:
     ```bash
     ffmpeg -loglevel error \
            -protocol_whitelist file,udp,rtp,srtp,crypto \
            -fflags nobuffer \
            -flags low_delay \
            -use_wallclock_as_timestamps 1 \
            -i /tmp/ave_video44_audio_XXXXXX.sdp \
            -f s16le \
            -acodec pcm_s16le \
            -ac 1 \
            -ar 8000 \
            -
     ```
   - I log mascherano rigorosamente qualsiasi parametro contenente chiavi o token (`inline:`, `key=`, `secret`).
5. **Stdout Reader Loop & Dispatch**:
   - Un task asincrono dedicato `_ffmpeg_audio_stdout_loop` legge dallo `stdout` del sottoprocesso blocchi fissi di **320 byte** (corrispondenti a 160 campioni a 16 bit mono a 8000 Hz, pari a 20 ms di audio).
   - I chunk vengono inoltrati a tutti i listener registrati tramite `_rx_pcm16_callbacks`.
   - Se nessun client è iscritto, i pacchetti vengono scartati senza accumulo in memoria per preservare la RAM.
6. **Distribuzione WebSocket (`ws_audio_subscribe`)**:
   - La funzione `ws_audio_subscribe` in `websocket_api.py` converte il blocco binario in Base64 e lo trasmette al client connesso:
     ```python
     b64_payload = base64.b64encode(pcm16_frame).decode("ascii")
     connection.send_event(msg["id"], {"payload": b64_payload})
     ```

### 4.2. Flusso Audio TX (Outbound: Client -> Citofono)

1. **Ricezione Frame WebSocket (`ws_audio_tx`)**:
   - Il client invia periodicamente (ogni 20 ms) un messaggio di tipo `ave_video44/audio_tx` contenente il chunk PCM16 codificato in Base64 (lunghezza tipica: 320 byte decodificati).
2. **Risoluzione della Sessione SIP Attiva**:
   - In `websocket_api.py`, la sessione attiva viene determinata in modo dinamico e univoco:
     ```python
     def get_active_sip_session(coordinator: AveVideo44Coordinator, device_id: Any):
         dev_str = str(device_id)
         # 1. Se esiste una CloudSipMediaSession attiva per il dispositivo, usa quella
         cloud_sess = coordinator.cloud_sip_sessions.get(dev_str)
         if cloud_sess and cloud_sess.is_active:
             return cloud_sess
         # 2. Fallback su AveSipSession per impianti solo LAN
         if coordinator.sip_session and not coordinator.sip_session.is_closed:
             return coordinator.sip_session
         return None
     ```
3. **Packetizer SRTP Outbound**:
   - In `CloudSipMediaSession`, il metodo `send_pcm16_frame(frame: bytes)` converte il frame PCM16 a 8000 Hz nel codec negoziato (G.711 u-law o A-law).
   - Il payload G.711 viene impacchettato con header RTP standard (RFC 3550): Payload Type `0` o `8`, sequenza incrementale `_tx_seq`, timestamp incrementato di 160 unità per frame e SSRC fisso di sessione.
   - Il pacchetto RTP viene crittografato secondo la specifica SRTP (RFC 3711) utilizzando la chiave locale generata per la sessione e inviato via `_audio_sock` a `(remote_ip, remote_audio_port)`.

---

## 5. Architettura Frontend: `ave-video44-card.js`

Il frontend è eseguito sia all'interno di normali browser web (Chrome, Firefox, Safari) che nell'ambiente integrato **Android System WebView** della Home Assistant Companion App.

### 5.1. Invarianti Rigorose WebView Android
Molti dispositivi a parete e tablet Android montano versioni datate del componente WebView (es. Android System WebView < 80). Per prevenire crash di parsing sintattico che renderebbero la card completamente invisibile (schermo bianco o errore "Custom element doesn't exist"):
- **DIVIETO ASSOLUTO dell'operatore Optional Chaining (`?.`)**: qualsiasi accesso a proprietà annidate deve usare controlli espliciti (`if (a && a.b && a.b.c)`).
- **DIVIETO ASSOLUTO dell'operatore Nullish Coalescing (`??`)**: qualsiasi fallback di valore deve usare l'operatore logico OR (`value !== undefined && value !== null ? value : defaultVal` oppure `a !== null && a !== void 0 ? a : b`).
- **Nessuna funzione ES2020+ non supportata**: utilizzo rigoroso di costrutti ES6 standard (Promesse, classi standard, arrow functions).

### 5.2. Inizializzazione `AudioContext` su User Gesture
I browser moderni e le WebView applicano la **WebAudio Autoplay Policy**: un `AudioContext` creato o avviato al di fuori di un evento utente diretto (click o tap) rimane nello stato `suspended` e genera warning in console, bloccando l'emissione audio.
- L'istanza di `AudioContext` non viene mai istanziata nel costruttore o nel lifecycle `connectedCallback`.
- Viene creata o riattivata esclusivamente all'interno degli handler di click: `_answer()`, `_callIntercom()` o `_monitor()`.
- Se l'istanza si trova in stato `suspended`, viene invocato `await this._audioCtx.resume()` prima di avviare nodi audio o riprodurre buffer.

```javascript
// Inizializzazione conforme
if (!this._audioCtx || this._audioCtx.state === "closed") {
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass) {
    this._showError("WebAudio API non supportata da questo browser");
    return;
  }
  this._audioCtx = new AudioContextClass();
}
if (this._audioCtx.state === "suspended") {
  await this._audioCtx.resume();
}
```

### 5.3. Pipeline Audio TX: Acquisizione, Downsampling e Invio
1. **Acquisizione Microfono**:
   ```javascript
   this._mediaStream = await navigator.mediaDevices.getUserMedia({
     audio: {
       channelCount: 1,
       echoCancellation: true,
       noiseSuppression: true,
       autoGainControl: true
     },
     video: false
   });
   ```
2. **Ricampionamento Dinamico Verso 8000 Hz**:
   - La frequenza nativa di campionamento dell'hardware audio del dispositivo è solitamente a 44100 Hz o 48000 Hz.
   - La funzione `_resampleTo8kPcm16` applica un'interpolazione lineare di decimazione per portare i campioni a 8000 Hz con quantizzazione Int16 a 16 bit signed:
     $$S_{16} = \max(-32768, \min(32767, \lfloor S \cdot 32767 \rfloor))$$
3. **Chunking da 20 ms**:
   - I campioni a 8 kHz vengono raccolti in un accumulatore circolare.
   - Non appena sono disponibili 160 campioni (320 byte), viene generato un messaggio WebSocket contenente il payload codificato in Base64:
     ```javascript
     this._hass.connection.sendMessage({
       type: "ave_video44/audio_tx",
       device_id: this._config.device_id,
       payload: base64Chunk
     });
     ```

### 5.4. Pipeline Audio RX: Jitter Buffer & Playback Continuo
La semplice riproduzione immediata di ogni frammento PCM16 ricevuto tramite `AudioBufferSourceNode.start()` provoca discontinuità acustiche ("crackling" o "jitter") dovute a variazioni di latenza della rete Wi-Fi o del tunnel Tailscale.

La card implementa un **Jitter Buffer temporale con scheduling anticipato**:
- **Target Buffer**: 120 ms (circa 6 frame da 20 ms).
- **Tracciamento Temporale**: Viene mantenuto un puntatore `_nextScheduledPlayTime` basato su `audioCtx.currentTime`.
- **Algoritmo di Schedulazione**:
  1. All'arrivo del primo frame audio, `_nextScheduledPlayTime = audioCtx.currentTime + 0.120` (buffer di sicurezza).
  2. Per ogni frame PCM16 decodificato ricevuto da `ws_audio_subscribe`:
     - Viene creato un `AudioBuffer` a 8000 Hz della durata del chunk (20 ms = 0.020 s).
     - Se `_nextScheduledPlayTime < audioCtx.currentTime` (sotto-alimentazione o freeze), il puntatore viene riallineato a `audioCtx.currentTime + 0.040`.
     - Il nodo sorgente viene avviato a `_nextScheduledPlayTime`:
       ```javascript
       sourceNode.start(this._nextScheduledPlayTime);
       this._nextScheduledPlayTime += buffer.duration;
       ```
  3. Questo garantisce un flusso continuo senza sovrapposizioni e privo di click tra frame contigui.

---

## 6. Piano di Collaudo e Telemetria

### 6.1. Misurazione RMS dei Livelli Audio
Per diagnosticare in tempo reale guasti al microfono del posto esterno o dello smartphone, il sistema calcola il valore RMS (Root Mean Square) del segnale:

$$\text{RMS} = \sqrt{\frac{1}{N} \sum_{i=1}^{N} x_i^2}$$
$$\text{Livello (dBFS)} = 20 \log_{10}\left(\frac{\text{RMS}}{32767}\right)$$

- **Backend (Python)**:
  - Calcolato ogni 100 frame su pacchetti decodificati da FFmpeg (RX) e in ricezione da WS (TX).
  - Valori tipici di riferimento:
    - Silenzio / Rumore di fondo: $< -45\text{ dBFS}$
    - Parlato normale: tra $-25\text{ dBFS}$ e $-12\text{ dBFS}$
    - Clipping / Saturazione: $> -1\text{ dBFS}$
- **Frontend (JavaScript)**:
  - Misurazione RMS sul buffer di input del microfono per fornire feedback visivo all'utente (barra verde di intensità vocale nella card).

### 6.2. Telemetria Low-Overhead
I log di debug vengono limitati per evitare saturazione di I/O disco e CPU su host Home Assistant a risorse ridotte (es. Raspberry Pi 4 o Home Assistant Green):
- Frequenza fissa di campionamento log: **una volta ogni 5.0 secondi**.
- Metriche aggregate emesse:
  - `audio_rx`: frame totali ricevuti, byte totali, rate in frame per secondo (fps, nominale 50.0 fps), RMS medio.
  - `audio_tx`: frame totali inviati, byte totali, rate in fps, latenza media di enqueue.
  - Eventuali drop per superamento della capacità massima della coda (coda limitata a 10 frame, pari a 200 ms).

```text
2026-10-26 18:30:05.123 DEBUG (MainThread) [custom_components.ave_video44.websocket_api] audio_rx device=1 frames=250 bytes=80000 rate=50.0 fps rms=-18.4 dBFS
2026-10-26 18:30:05.125 DEBUG (MainThread) [custom_components.ave_video44.websocket_api] audio_tx device=1 frames=248 bytes=79360 rate=49.6 fps rms=-21.1 dBFS
```

### 6.3. Matrice dei Casi di Test

| ID Test | Ambiente / Dispositivo | Connessione | Azione | Esito Atteso |
| :--- | :--- | :--- | :--- | :--- |
| **TC-01** | Desktop PC (senza microfono) | LAN Cablata | Click su "Attiva video" | Stream video attivo, audio RX chiaro dall'altoparlante, zero errori console, nessun prompt microfono. |
| **TC-02** | Desktop PC (senza microfono) | LAN Cablata | Click su "Rispondi" | Notifica *"Solo ascolto"*, video e audio RX attivi, pulsante Muto disabilitato, zero crash. |
| **TC-03** | Laptop (con microfono) | Wi-Fi Locale | Click su "Chiama" | Audio full-duplex attivo, RMS vocale visibile, voce udita chiaramente dal posto esterno. |
| **TC-04** | Android Companion App | Wi-Fi Locale | Click su "Rispondi" | Autoplay AudioContext sbloccato regolarmente, assenza di eco acustico (AEC hardware attivo). |
| **TC-05** | Android Companion App | Tailscale VPN (4G) | Click su "Attiva video" | Jitter buffer compensa la latenza mobile (~70 ms), audio RX fluido senza click né salti. |
| **TC-06** | Qualsiasi client | Qualsiasi | Pressione "Pedonale" durante chiamata | Sblocco serratura immediato, nessun gap o interruzione su audio o video. |
| **TC-07** | Qualsiasi client | Qualsiasi | Pressione "Chiudi" | Teardown completo entro 500 ms: terminazione subprocessi FFmpeg, chiusura socket e WS. |

---

## 7. Rischi, Mitigazioni e Piano di Rollback

### 7.1. Matrice dei Rischi e Mitigazioni

| Rischio Identificato | Probabilità | Impatto | Strategia di Mitigazione |
| :--- | :---: | :---: | :--- |
| **Overhead CPU per doppio FFmpeg (Video + Audio)** | Media | Medio | L'audio FFmpeg usa parametri ultraleggeri (`-acodec pcm_s16le -ar 8000`), con consumo CPU $< 1\%$ su architetture quad-core ARM. L'audio subprocess si avvia solo quando la sessione multimediale è attiva. |
| **Eco Acustico su Smartphone** | Alta | Medio | Forzatura dei constraint WebAudio: `echoCancellation: true`, `noiseSuppression: true`, `autoGainControl: true`. Utilizzo del microfono di sistema calibrato dall'OS mobile. |
| **Blocco Sintattico WebView Android** | Alta | Alto | Divieto categorico di costrutti moderni `?.` e `??`. Verifica automatica tramite script di validazione sintattica pre-commit. |
| **Desincronizzazione Audio/Video** | Bassa | Basso | Video e audio condividono la medesima sessione SIP ma viaggiano su socket separati. Il jitter buffer frontend a 120 ms garantisce un perfetto allineamento percettivo. |
| **Mancato Rilascio Risorse Socket** | Bassa | Medio | `async_stop()` garantisce la chiusura in blocco di `_audio_sock`, distruzione del subprocess FFmpeg con `SIGTERM`/`SIGKILL` e rimozione dei file temporanei `.sdp`. |

### 7.2. Piano di Rollback
Qualora l'implementazione dell'audio introducesse instabilità o regressioni impreviste:
1. **Disattivazione Feature via Configurazione**:
   - Predisporre una flag di compatibilità `enable_audio: false` nelle opzioni dell'integrazione (`OptionsFlow`).
   - Se disabilitata, `CloudSipMediaSession` e `websocket_api.py` disattivano il relay audio e l'avvio del sottoprocesso FFmpeg audio, tornando alla modalità operativa pura video + controllo.
2. **Rollback del Frontend**:
   - In caso di anomalie di compatibilità WebView, ripristinare la versione precedente di `ave-video44-card.js` incrementando il parametro `version` per forzare il refresh della cache nei client Lovelace.
3. **Isolamento dell'Infrastruttura Video**:
   - La gestione del socket video (`_video_sock`), del descrittore SDP video e del decoder H.264 rimane completamente separata dal ciclo di vita dell'audio subprocess, scongiurando qualsiasi rischio di disservizio sul video stream.
