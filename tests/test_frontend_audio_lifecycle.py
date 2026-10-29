from pathlib import Path


def test_frontend_audio_rx_resumes_suspended_context_and_guards_subscription():
    card_js = Path("custom_components/ave_video44/frontend/ave-video44-card.js").read_text(encoding="utf-8")
    play_idx = card_js.index("_playIncomingPcm16(pcm16Array)")
    play_block = card_js[play_idx : play_idx + 900]
    assert 'this._audioCtx.state === "suspended"' in play_block
    assert "this._audioCtx.resume()" in play_block
    assert "this._nextScheduledPlayTime = 0" in play_block

    sub_idx = card_js.index("async _subscribeAudioRx()")
    sub_block = card_js[sub_idx : sub_idx + 700]
    assert "this._audioSubUnsubscribe" in sub_block
    assert "this._ensureAudioContext()" in sub_block
