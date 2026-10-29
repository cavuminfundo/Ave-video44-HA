"""Tests for AVE Video V44 Lovelace Card WebAudio and Session Activation.

TDD tests verifying:
- Synchronous WebAudio unlock before first await in user action handlers
- Correct activation ordering in _answer() and _callIntercom()
- Continuous PCM16 playback without dropping frames or resetting scheduling cursor
- Reuse of _ensureAudioContext() across TX and RX lifecycles
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
CARD_PATH = REPO_ROOT / "custom_components" / "ave_video44" / "frontend" / "ave-video44-card.js"


def _extract_method(content: str, method_name: str) -> str:
    """Extract method definition and body by matching balanced braces."""
    pattern = rf"(async\s+{re.escape(method_name)}\s*\([^)]*\)\s*\{{|{re.escape(method_name)}\s*\([^)]*\)\s*\{{)"
    match = re.search(pattern, content)
    if not match:
        raise ValueError(f"Method {method_name} not found in card source")
    start_pos = match.end() - 1
    depth = 0
    end_pos = start_pos
    for idx in range(start_pos, len(content)):
        char = content[idx]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end_pos = idx + 1
                break
    return content[start_pos:end_pos]


def test_user_actions_ensure_audio_context_synchronously() -> None:
    """_monitor, _answer, _callIntercom, and _toggleMute must call _ensureAudioContext synchronously before first await."""
    card_js = CARD_PATH.read_text(encoding="utf-8")
    monitored_methods = ["_monitor", "_answer", "_callIntercom", "_toggleMute"]

    for method in monitored_methods:
        body = _extract_method(card_js, method)
        assert "this._ensureAudioContext()" in body, (
            f"{method} must call this._ensureAudioContext() to unlock WebAudio on user gesture"
        )
        ensure_idx = body.index("this._ensureAudioContext()")
        if "await " in body:
            first_await_idx = body.index("await ")
            assert ensure_idx < first_await_idx, (
                f"{method} must call this._ensureAudioContext() synchronously before the first await"
            )


def test_answer_order_call_control_before_rx_and_tx() -> None:
    """_answer must send ave_video44/call_control before subscribing RX and starting TX."""
    card_js = CARD_PATH.read_text(encoding="utf-8")
    body = _extract_method(card_js, "_answer")

    assert 'action: "answer"' in body
    assert "this._config.device_id" in body
    assert "this._subscribeAudioRx()" in body
    assert "this._startAudioTx()" in body

    ctrl_idx = body.index('action: "answer"')
    rx_idx = body.index("this._subscribeAudioRx()")
    tx_idx = body.index("this._startAudioTx()")

    assert ctrl_idx < rx_idx, "_answer must send call_control answer before subscribing to audio RX"
    assert ctrl_idx < tx_idx, "_answer must send call_control answer before starting audio TX"


def test_call_intercom_order_service_before_rx_and_tx() -> None:
    """_callIntercom must await callService('ave_video44', 'call_intercom') before RX and TX."""
    card_js = CARD_PATH.read_text(encoding="utf-8")
    body = _extract_method(card_js, "_callIntercom")

    assert 'callService("ave_video44", "call_intercom"' in body
    assert "this._subscribeAudioRx()" in body
    assert "this._startAudioTx()" in body

    svc_idx = body.index('callService("ave_video44", "call_intercom"')
    rx_idx = body.index("this._subscribeAudioRx()")
    tx_idx = body.index("this._startAudioTx()")

    assert svc_idx < rx_idx, "_callIntercom must call call_intercom before subscribing to audio RX"
    assert svc_idx < tx_idx, "_callIntercom must call call_intercom before starting audio TX"


def test_play_incoming_pcm16_does_not_drop_or_reset_cursor_when_suspended() -> None:
    """_playIncomingPcm16 must not drop frames with return or reset nextScheduledPlayTime on suspended context."""
    card_js = CARD_PATH.read_text(encoding="utf-8")
    body = _extract_method(card_js, "_playIncomingPcm16")

    assert 'this._audioCtx.state === "suspended"' in body
    assert "this._audioCtx.resume()" in body

    suspended_match = re.search(r'if\s*\([^)]*state === "suspended"[^)]*\)\s*\{([^}]*)\}', body)
    assert suspended_match is not None, "Suspended state handling block must exist"
    suspended_block = suspended_match.group(1)

    assert "return" not in suspended_block, "_playIncomingPcm16 must not return early on suspended state"
    assert "_nextScheduledPlayTime" not in suspended_block, (
        "_playIncomingPcm16 must not reset _nextScheduledPlayTime when suspended"
    )
    assert "this._nextScheduledPlayTime = 0" not in body, (
        "_playIncomingPcm16 must not reset this._nextScheduledPlayTime = 0"
    )


def test_start_audio_tx_reuses_ensure_audio_context() -> None:
    """_startAudioTx should reuse this._ensureAudioContext() instead of duplicating AudioContext setup."""
    card_js = CARD_PATH.read_text(encoding="utf-8")
    body = _extract_method(card_js, "_startAudioTx")

    assert "this._ensureAudioContext()" in body, "_startAudioTx must reuse this._ensureAudioContext()"
    assert "new AudioContextClass()" not in body, "_startAudioTx must not duplicate AudioContext constructor"


if __name__ == "__main__":
    tests = [
        test_user_actions_ensure_audio_context_synchronously,
        test_answer_order_call_control_before_rx_and_tx,
        test_call_intercom_order_service_before_rx_and_tx,
        test_play_incoming_pcm16_does_not_drop_or_reset_cursor_when_suspended,
        test_start_audio_tx_reuses_ensure_audio_context,
    ]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
        except AssertionError as err:
            print(f"FAIL (RED as expected): {t.__name__}: {err}")
            failed += 1
        except Exception as err:
            print(f"ERROR: {t.__name__}: {err}")
            failed += 1
    print(f"\nTotal: {len(tests)}, Failed: {failed}")
    if failed > 0:
        raise SystemExit(1)
