from pathlib import Path


CARD_JS_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "ave_video44"
    / "frontend"
    / "ave-video44-card.js"
)


def test_lovelace_card_auto_resolves_device_id_from_entities():
    src = CARD_JS_PATH.read_text(encoding="utf-8")
    auto_resolve_block = src.split("_autoResolveEntities(hass) {")[1].split("connectedCallback()")[0]
    assert "if (!this._config.device_id)" in auto_resolve_block
    assert "attributes.device_id" in auto_resolve_block
    assert "this._config.device_id = String(" in auto_resolve_block


def test_lovelace_card_call_intercom_starts_bidirectional_audio_without_monitor_hijack():
    src = CARD_JS_PATH.read_text(encoding="utf-8")
    call_block = src.split("async _callIntercom() {")[1].split("_arrayBufferToBase64")[0]
    assert "this._monitor();" not in call_block
    assert "await this._subscribeAudioRx();" in call_block
    assert "await this._startAudioTx();" in call_block
    assert "cameraStreamImg" in call_block


def test_lovelace_card_monitoring_subscribes_audio_rx_and_shows_hangup():
    src = CARD_JS_PATH.read_text(encoding="utf-8")
    hass_block = src.split("set hass(hass) {")[1].split("_checkAutoAnswer()")[0]
    monitoring_branch = hass_block.split('callSensorState === "monitoring"')[1]
    assert "this._subscribeAudioRx();" in monitoring_branch

    update_view_block = src.split("_updateView() {")[1].split("_ensureAudioContext()")[0]
    hangup_branch = update_view_block.split('getElementById("btnHangup")')[1].split("btnMute")[0]
    assert 'this._callState === "talking" || this._callState === "ringing" || this._callState === "monitoring"' in hangup_branch


def test_lovelace_card_jitter_buffer_caps_drift_at_250ms_and_drops_excess_burst():
    src = CARD_JS_PATH.read_text(encoding="utf-8")
    play_block = src.split("_playIncomingPcm16(pcm16Array) {")[1].split("_cleanupCall()")[0]
    assert "const maxDrift = 0.250;" in play_block
    assert "this._nextScheduledPlayTime - now > maxDrift" in play_block
    assert "return;" in play_block

