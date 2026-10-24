// Design Read: Intercom Card UI for Home Assistant Lovelace & Companion App, technical utility dark theme, dial ENERGY 1 / RHYTHM 1 / MOTION 1

const CARD_VERSION = "1.0.0";

class AveVideo44Card extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
    this._inCall = false;
    this._callState = "idle";
    this._isMuted = false;
    this._mediaStream = null;
    this._audioCtx = null;
    this._audioWorkletNode = null;
    this._scriptProcessor = null;
    this._audioSubUnsubscribe = null;
    this._lastStateSignature = "";
    this._autoAnswerChecked = false;
    this._boundKeyDown = this._handleKeyDown.bind(this);
  }

  static getStubConfig() {
    return {
      entity: "camera.posto_esterno_ingresso",
      device_id: "doorstation_001",
      intercom_select: "select.rubrica_interni",
      call_state_sensor: "sensor.posto_esterno_stato_chiamata",
      doorbell_binary_sensor: "binary_sensor.posto_esterno_chiamata_in_corso",
      lock_pedestrian: "lock.posto_esterno_cancelletto_pedonale",
      lock_driveway: "lock.posto_esterno_cancello_carraio"
    };
  }

  setConfig(config) {
    if (!config.device_id && !config.entity) {
      throw new Error("ave-video44-card requires device_id or entity");
    }
    this._config = {
      title: "AVE Video V44",
      device_id: "doorstation_001",
      ...config
    };
    this._renderBase();
  }

  connectedCallback() {
    window.addEventListener("keydown", this._boundKeyDown);
    this._checkAutoAnswer();
  }

  disconnectedCallback() {
    window.removeEventListener("keydown", this._boundKeyDown);
    this._cleanupCall();
  }

  _handleKeyDown(event) {
    if (event.key === "Escape" && this._inCall) {
      this._hangup();
    }
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._config || !hass) return;

    const cameraState = (this._config.entity && hass.states[this._config.entity]) ? hass.states[this._config.entity].state : "";
    const callSensorState = (this._config.call_state_sensor && hass.states[this._config.call_state_sensor]) ? hass.states[this._config.call_state_sensor].state : "";
    const doorbellState = (this._config.doorbell_binary_sensor && hass.states[this._config.doorbell_binary_sensor]) ? hass.states[this._config.doorbell_binary_sensor].state : "";
    const selectState = (this._config.intercom_select && hass.states[this._config.intercom_select]) ? hass.states[this._config.intercom_select].state : "";

    const signature = `${cameraState}|${callSensorState}|${doorbellState}|${selectState}|${this._callState}|${this._inCall}`;
    if (signature === this._lastStateSignature) {
      return;
    }
    this._lastStateSignature = signature;

    if (doorbellState === "on" || callSensorState === "ringing") {
      if (this._callState !== "talking" && this._callState !== "ringing") {
        this._setCallState("ringing");
      }
    } else if (callSensorState === "talking") {
      if (this._callState !== "talking") {
        this._setCallState("talking");
      }
    } else if (this._callState !== "idle" && (callSensorState === "idle" || (!callSensorState && doorbellState === "off"))) {
      if (this._inCall) {
        this._cleanupCall();
      }
      this._setCallState("idle");
    }

    this._updateDynamicContent();
    this._checkAutoAnswer();
  }

  _checkAutoAnswer() {
    if (this._autoAnswerChecked || !this._hass || !this._config) return;
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const action = urlParams.get("ave_call");
      const targetDevice = urlParams.get("device_id");

      if (action === "answer" && (!targetDevice || targetDevice === this._config.device_id)) {
        this._autoAnswerChecked = true;
        this._answer();
      }
    } catch (_) {}
  }

  _setCallState(newState) {
    this._callState = newState;
    this._inCall = (newState === "ringing" || newState === "talking");
    this._updateView();
  }

  _renderBase() {
    const shadow = this.shadowRoot;
    shadow.innerHTML = `
      <style>
        :host {
          --ave-bg-primary: #18181b;
          --ave-bg-surface: #27272a;
          --ave-text-primary: #f4f4f5;
          --ave-text-secondary: #a1a1aa;
          --ave-accent-answer: #047857;
          --ave-accent-hangup: #dc2626;
          --ave-accent-blue: #2563eb;
          --ave-focus-ring: #60a5fa;
          display: block;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
          box-sizing: border-box;
        }

        .card-container {
          background-color: var(--ave-bg-primary);
          color: var(--ave-text-primary);
          border-radius: 12px;
          overflow: hidden;
          border: 1px solid var(--ave-bg-surface);
          box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
          position: relative;
        }

        .card-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 14px 16px;
          background-color: var(--ave-bg-surface);
          border-bottom: 1px solid #3f3f46;
        }

        .card-title-group {
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .card-title {
          font-size: 1rem;
          font-weight: 600;
          margin: 0;
          color: var(--ave-text-primary);
        }

        .status-badge {
          font-size: 0.75rem;
          font-weight: 500;
          padding: 3px 8px;
          border-radius: 9999px;
          background: #3f3f46;
          color: var(--ave-text-primary);
        }

        .status-badge.ringing {
          background-color: var(--ave-accent-answer);
          color: #ffffff;
        }

        .status-badge.talking {
          background-color: var(--ave-accent-blue);
          color: #ffffff;
        }

        .status-badge.error {
          background-color: var(--ave-accent-hangup);
          color: #ffffff;
        }

        .video-container {
          position: relative;
          width: 100%;
          aspect-ratio: 16 / 9;
          background-color: #09090b;
          display: flex;
          align-items: center;
          justify-content: center;
          overflow: hidden;
        }

        .video-element {
          width: 100%;
          height: 100%;
          object-fit: cover;
        }

        .video-placeholder {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 8px;
          color: var(--ave-text-secondary);
        }

        .caller-banner {
          position: absolute;
          top: 12px;
          left: 12px;
          right: 12px;
          padding: 8px 12px;
          background: rgba(24, 24, 27, 0.85);
          backdrop-filter: blur(4px);
          border-radius: 6px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          font-size: 0.875rem;
          z-index: 5;
        }

        .controls-panel {
          padding: 16px;
          display: flex;
          flex-direction: column;
          gap: 12px;
          background-color: var(--ave-bg-primary);
        }

        .button-group {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
          gap: 8px;
        }

        button {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          padding: 10px 14px;
          font-size: 0.875rem;
          font-weight: 500;
          border-radius: 6px;
          border: 1px solid transparent;
          cursor: pointer;
          transition: background-color 0.15s ease, border-color 0.15s ease;
          outline: none;
        }

        button:focus-visible {
          box-shadow: 0 0 0 3px var(--ave-focus-ring);
        }

        .btn-surface {
          background-color: var(--ave-bg-surface);
          color: var(--ave-text-primary);
          border-color: #3f3f46;
        }

        .btn-surface:hover {
          background-color: #3f3f46;
        }

        .btn-answer {
          background-color: var(--ave-accent-answer);
          color: #ffffff;
        }

        .btn-answer:hover {
          background-color: #065f46;
        }

        .btn-hangup {
          background-color: var(--ave-accent-hangup);
          color: #ffffff;
        }

        .btn-hangup:hover {
          background-color: #b91c1c;
        }

        .btn-blue {
          background-color: var(--ave-accent-blue);
          color: #ffffff;
        }

        .btn-blue:hover {
          background-color: #1d4ed8;
        }

        .intercom-row {
          display: flex;
          gap: 8px;
          align-items: center;
          margin-top: 4px;
        }

        select {
          flex: 1;
          padding: 9px 12px;
          border-radius: 6px;
          background-color: var(--ave-bg-surface);
          color: var(--ave-text-primary);
          border: 1px solid #3f3f46;
          font-size: 0.875rem;
          outline: none;
        }

        select:focus-visible {
          border-color: var(--ave-focus-ring);
          box-shadow: 0 0 0 2px var(--ave-focus-ring);
        }

        .hidden {
          display: none !important;
        }

        .feedback-banner {
          padding: 8px 12px;
          border-radius: 6px;
          font-size: 0.8125rem;
          margin-bottom: 8px;
        }

        .feedback-banner.error {
          background-color: rgba(220, 38, 38, 0.2);
          border: 1px solid var(--ave-accent-hangup);
          color: #fca5a5;
        }
      </style>

      <div class="card-container" id="mainContainer" role="region" aria-label="Videocitofono AVE">
        <header class="card-header">
          <div class="card-title-group">
            <ha-icon icon="mdi:doorbell-video"></ha-icon>
            <h2 class="card-title" id="cardTitle"></h2>
          </div>
          <span class="status-badge" id="statusBadge" role="status"></span>
        </header>

        <div id="feedbackBanner" class="feedback-banner hidden" role="alert"></div>

        <div class="video-container" id="videoBox">
          <div class="caller-banner hidden" id="callerBanner">
            <span id="callerNameText"></span>
            <span id="callDurationText">00:00</span>
          </div>

          <div class="video-placeholder" id="videoPlaceholder">
            <ha-icon icon="mdi:cctv" style="--mdc-icon-size: 48px;"></ha-icon>
            <span id="placeholderText">Anteprima telecamera in caricamento</span>
          </div>

          <img id="cameraStreamImg" class="video-element hidden" alt="Live Camera Feed" />
          <video id="liveVideo" class="video-element hidden" autoplay playsinline muted></video>
        </div>

        <div class="controls-panel">
          <div id="inCallControls" class="button-group hidden">
            <button id="btnAnswer" class="btn-answer" aria-label="Rispondi alla chiamata">
              <ha-icon icon="mdi:phone"></ha-icon>
              <span>Rispondi</span>
            </button>
            <button id="btnHangup" class="btn-hangup" aria-label="Chiudi o rifiuta la chiamata">
              <ha-icon icon="mdi:phone-hangup"></ha-icon>
              <span>Rifiuta</span>
            </button>
            <button id="btnMute" class="btn-surface" aria-label="Attiva o disattiva microfono">
              <ha-icon id="muteIcon" icon="mdi:microphone"></ha-icon>
              <span id="muteLabel">Muto</span>
            </button>
            <button id="btnUnlockInCall" class="btn-surface" aria-label="Apri cancelletto pedonale">
              <ha-icon icon="mdi:door-open"></ha-icon>
              <span>Apri Porta</span>
            </button>
          </div>

          <div id="idleControls" class="button-group">
            <button id="btnUnlockPedestrian" class="btn-surface" aria-label="Apri cancelletto pedonale">
              <ha-icon icon="mdi:door"></ha-icon>
              <span>Apri Cancelletto</span>
            </button>
            <button id="btnUnlockDriveway" class="btn-surface" aria-label="Apri cancello carraio">
              <ha-icon icon="mdi:gate"></ha-icon>
              <span>Apri Cancello</span>
            </button>
          </div>

          <div class="intercom-row" id="intercomRow">
            <label for="intercomSelect" class="sr-only" style="display:none">Rubrica Interni</label>
            <select id="intercomSelect" aria-label="Seleziona interno per chiamata"></select>
            <button id="btnCallIntercom" class="btn-blue" aria-label="Avvia chiamata all'interno selezionato">
              <ha-icon icon="mdi:phone-outgoing"></ha-icon>
              <span>Chiama</span>
            </button>
          </div>
        </div>
      </div>
    `;

    this._setupListeners();
    this._updateDynamicContent();
  }

  _setupListeners() {
    const shadow = this.shadowRoot;
    shadow.getElementById("btnAnswer").addEventListener("click", () => this._answer());
    shadow.getElementById("btnHangup").addEventListener("click", () => this._hangup());
    shadow.getElementById("btnMute").addEventListener("click", () => this._toggleMute());
    shadow.getElementById("btnUnlockInCall").addEventListener("click", () => this._unlock("1"));
    shadow.getElementById("btnUnlockPedestrian").addEventListener("click", () => this._unlock("1"));
    shadow.getElementById("btnUnlockDriveway").addEventListener("click", () => this._unlock("2"));
    shadow.getElementById("btnCallIntercom").addEventListener("click", () => this._callIntercom());
  }

  _updateDynamicContent() {
    const shadow = this.shadowRoot;
    if (!shadow) return;

    const titleEl = shadow.getElementById("cardTitle");
    if (titleEl) {
      titleEl.textContent = this._config.title || "AVE Video V44";
    }

    const badgeEl = shadow.getElementById("statusBadge");
    if (badgeEl) {
      badgeEl.className = `status-badge ${this._callState}`;
      if (this._callState === "ringing") {
        badgeEl.textContent = "Chiamata in arrivo";
      } else if (this._callState === "talking") {
        badgeEl.textContent = "In conversazione";
      } else if (this._callState === "error") {
        badgeEl.textContent = "Errore linea";
      } else if (this._callState === "loading") {
        badgeEl.textContent = "Caricamento...";
      } else {
        badgeEl.textContent = "A riposo";
      }
    }

    const selectEl = shadow.getElementById("intercomSelect");
    if (selectEl && this._hass && this._config.intercom_select) {
      const selectEntity = this._hass.states[this._config.intercom_select];
      if (selectEntity && selectEntity.attributes && selectEntity.attributes.options) {
        const options = selectEntity.attributes.options;
        const currentVal = selectEl.value;
        selectEl.textContent = "";
        options.forEach((opt) => {
          const optEl = document.createElement("option");
          optEl.value = opt;
          optEl.textContent = opt;
          selectEl.appendChild(optEl);
        });
        if (currentVal && options.includes(currentVal)) {
          selectEl.value = currentVal;
        } else if (selectEntity.state && options.includes(selectEntity.state)) {
          selectEl.value = selectEntity.state;
        }
      }
    }

    const callerNameEl = shadow.getElementById("callerNameText");
    if (callerNameEl) {
      callerNameEl.textContent = `Chiamante: ${this._config.device_id || "Posto Esterno"}`;
    }
  }

  _updateView() {
    const shadow = this.shadowRoot;
    if (!shadow) return;

    const inCallControls = shadow.getElementById("inCallControls");
    const idleControls = shadow.getElementById("idleControls");
    const callerBanner = shadow.getElementById("callerBanner");
    const container = shadow.getElementById("mainContainer");
    const placeholderText = shadow.getElementById("placeholderText");
    const liveVideo = shadow.getElementById("liveVideo");
    const cameraStreamImg = shadow.getElementById("cameraStreamImg");
    const videoPlaceholder = shadow.getElementById("videoPlaceholder");

    this._updateDynamicContent();

    const cameraEntity = this._config.entity || this._config.camera_entity;
    if (cameraEntity && this._hass && this._hass.states[cameraEntity]) {
      const token = this._hass.states[cameraEntity].attributes ? this._hass.states[cameraEntity].attributes.access_token : "";
      const streamUrl = token
        ? `/api/camera_proxy_stream/${cameraEntity}?token=${token}`
        : `/api/camera_proxy/${cameraEntity}`;

      if (cameraStreamImg) {
        if (cameraStreamImg.src !== streamUrl) {
          cameraStreamImg.src = streamUrl;
        }
        cameraStreamImg.classList.remove("hidden");
      }
      if (liveVideo) {
        liveVideo.classList.remove("hidden");
      }
      if (videoPlaceholder) {
        videoPlaceholder.classList.add("hidden");
      }
    } else {
      if (cameraStreamImg) cameraStreamImg.classList.add("hidden");
      if (liveVideo) liveVideo.classList.add("hidden");
      if (videoPlaceholder) videoPlaceholder.classList.remove("hidden");
    }

    if (this._inCall) {
      container.setAttribute("role", "dialog");
      container.setAttribute("aria-modal", "true");
      container.setAttribute("aria-label", "Chiamata attiva videocitofono AVE");
      inCallControls.classList.remove("hidden");
      idleControls.classList.add("hidden");
      callerBanner.classList.remove("hidden");
      if (placeholderText) {
        placeholderText.textContent = "Streaming audio/video in corso";
      }
    } else {
      container.removeAttribute("role");
      container.removeAttribute("aria-modal");
      container.removeAttribute("aria-label");
      inCallControls.classList.add("hidden");
      idleControls.classList.remove("hidden");
      callerBanner.classList.add("hidden");
      if (placeholderText) {
        placeholderText.textContent = "Nessuna chiamata attiva";
      }
    }
  }

  async _answer() {
    this._setCallState("talking");
    try {
      await this._startAudioTx();
      await this._subscribeAudioRx();
      if (this._hass) {
        await this._hass.connection.sendMessagePromise({
          type: "ave_video44/call_control",
          device_id: this._config.device_id,
          action: "answer"
        });
      }
    } catch (err) {
      this._cleanupCall();
      this._showError(`Impossibile avviare audio: ${err.message}`);
      this._setCallState("error");
    }
  }

  async _hangup() {
    try {
      if (this._hass) {
        await this._hass.connection.sendMessagePromise({
          type: "ave_video44/call_control",
          device_id: this._config.device_id,
          action: "hangup"
        });
      }
    } catch (_) {
    } finally {
      this._cleanupCall();
      this._setCallState("idle");
    }
  }

  _toggleMute() {
    this._isMuted = !this._isMuted;
    const shadow = this.shadowRoot;
    const muteIcon = shadow.getElementById("muteIcon");
    const muteLabel = shadow.getElementById("muteLabel");

    if (this._mediaStream) {
      this._mediaStream.getAudioTracks().forEach((track) => {
        track.enabled = !this._isMuted;
      });
    }

    if (this._isMuted) {
      muteIcon.setAttribute("icon", "mdi:microphone-off");
      muteLabel.textContent = "Muto attivo";
    } else {
      muteIcon.setAttribute("icon", "mdi:microphone");
      muteLabel.textContent = "Muto";
    }
  }

  async _unlock(lockId) {
    if (!this._hass) return;
    try {
      await this._hass.connection.sendMessagePromise({
        type: "ave_video44/call_control",
        device_id: this._config.device_id,
        action: "unlock",
        lock_id: lockId
      });
    } catch (err) {
      this._showError(`Apertura non riuscita: ${err.message}`);
    }
  }

  async _callIntercom() {
    const shadow = this.shadowRoot;
    const selectEl = shadow.getElementById("intercomSelect");
    const target = selectEl ? selectEl.value : "";
    if (!target || !this._hass) return;

    try {
      await this._hass.callService("ave_video44", "call_intercom", {
        device_id: this._config.device_id,
        room_code: target
      });
      this._setCallState("talking");
    } catch (err) {
      this._showError(`Chiamata non riuscita: ${err.message}`);
    }
  }

  _arrayBufferToBase64(buffer) {
    let binary = "";
    const bytes = new Uint8Array(buffer);
    const len = bytes.byteLength;
    for (let i = 0; i < len; i++) {
      binary += String.fromCharCode(bytes[i]);
    }
    return window.btoa(binary);
  }

  _base64ToInt16Array(base64) {
    const binaryStr = window.atob(base64);
    const len = binaryStr.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
      bytes[i] = binaryStr.charCodeAt(i);
    }
    return new Int16Array(bytes.buffer);
  }

  async _startAudioTx() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error("Dispositivo senza supporto WebAudio getUserMedia");
    }

    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    this._audioCtx = new AudioContextClass();
    if (this._audioCtx.state === "suspended") {
      await this._audioCtx.resume();
    }

    this._mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      },
      video: false
    });

    const source = this._audioCtx.createMediaStreamSource(this._mediaStream);
    const bufferSize = 2048;
    this._scriptProcessor = this._audioCtx.createScriptProcessor(bufferSize, 1, 1);

    const inputSampleRate = this._audioCtx.sampleRate;

    this._scriptProcessor.onaudioprocess = (e) => {
      if (this._isMuted || !this._inCall || !this._hass) return;
      const inputData = e.inputBuffer.getChannelData(0);
      const pcm16Data = this._resampleTo8kPcm16(inputData, inputSampleRate);
      const base64Str = this._arrayBufferToBase64(pcm16Data.buffer);

      this._hass.connection.sendMessage({
        type: "ave_video44/audio_tx",
        device_id: this._config.device_id,
        payload: base64Str
      });
    };

    source.connect(this._scriptProcessor);
    this._scriptProcessor.connect(this._audioCtx.destination);
  }

  _resampleTo8kPcm16(inputBuffer, inputSampleRate) {
    const targetRate = 8000;
    if (inputSampleRate === targetRate) {
      const pcm16 = new Int16Array(inputBuffer.length);
      for (let i = 0; i < inputBuffer.length; i++) {
        const s = Math.max(-1, Math.min(1, inputBuffer[i]));
        pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      return pcm16;
    }

    const ratio = inputSampleRate / targetRate;
    const outputLength = Math.round(inputBuffer.length / ratio);
    const pcm16 = new Int16Array(outputLength);

    for (let i = 0; i < outputLength; i++) {
      const origIndex = Math.min(Math.round(i * ratio), inputBuffer.length - 1);
      const s = Math.max(-1, Math.min(1, inputBuffer[origIndex]));
      pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    return pcm16;
  }

  async _subscribeAudioRx() {
    if (!this._hass) return;
    try {
      this._audioSubUnsubscribe = await this._hass.connection.subscribeMessage(
        (msg) => {
          if (msg && this._audioCtx && this._inCall) {
            let pcmData = null;
            if (typeof msg.payload === "string") {
              pcmData = this._base64ToInt16Array(msg.payload);
            } else if (msg.pcm16) {
              pcmData = Array.isArray(msg.pcm16) ? new Int16Array(msg.pcm16) : msg.pcm16;
            }
            if (pcmData && pcmData.length > 0) {
              this._playIncomingPcm16(pcmData);
            }
          }
        },
        {
          type: "ave_video44/audio_subscribe",
          device_id: this._config.device_id
        }
      );
    } catch (_) {}
  }

  _playIncomingPcm16(pcm16Array) {
    if (!this._audioCtx || this._audioCtx.state === "closed") return;
    const buffer = this._audioCtx.createBuffer(1, pcm16Array.length, 8000);
    const channelData = buffer.getChannelData(0);
    for (let i = 0; i < pcm16Array.length; i++) {
      channelData[i] = pcm16Array[i] / 32768.0;
    }

    const source = this._audioCtx.createBufferSource();
    source.buffer = buffer;
    source.connect(this._audioCtx.destination);
    source.start();
  }

  _cleanupCall() {
    if (this._mediaStream) {
      this._mediaStream.getTracks().forEach((track) => track.stop());
      this._mediaStream = null;
    }
    if (this._scriptProcessor) {
      this._scriptProcessor.disconnect();
      this._scriptProcessor = null;
    }
    if (this._audioCtx) {
      this._audioCtx.close().catch(() => {});
      this._audioCtx = null;
    }
    if (this._audioSubUnsubscribe) {
      try {
        this._audioSubUnsubscribe();
      } catch (_) {}
      this._audioSubUnsubscribe = null;
    }
    this._isMuted = false;
    this._inCall = false;
    this._callState = "idle";
  }

  _showError(message) {
    const shadow = this.shadowRoot;
    const banner = shadow.getElementById("feedbackBanner");
    if (banner) {
      banner.textContent = message;
      banner.className = "feedback-banner error";
      setTimeout(() => {
        banner.className = "feedback-banner hidden";
      }, 5000);
    }
  }

  getCardSize() {
    return 4;
  }
}

customElements.define("ave-video44-card", AveVideo44Card);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "ave-video44-card",
  name: "AVE Video V44 Card",
  preview: true,
  description: "Card Lovelace interattiva per videocitofoni AVE Video V44 con audio full-duplex WebAudio."
});
