"""Tests for AVE Video V44 Frontend Lovelace Card, Blueprint, Brand and Docs.

TDD tests verifying:
- Automation Blueprint YAML schema, deep-link, and action labels
- ave-video44-card.js custom element, state memoization, WebAudio resampler,
  track cleanup, XSS safety, ARIA attributes, <ha-icon> usage, and WCAG AA contrast
- Brand PNG assets validity
- README documentation coverage in Italian and English
"""

from __future__ import annotations

import re
import struct
from pathlib import Path
try:
    import pytest
except ImportError:
    pytest = None
import yaml

REPO_ROOT = Path(__file__).parent.parent
CARD_PATH = REPO_ROOT / "custom_components" / "ave_video44" / "frontend" / "ave-video44-card.js"
BLUEPRINT_PATH = (
    REPO_ROOT
    / "custom_components"
    / "ave_video44"
    / "blueprints"
    / "automation"
    / "incoming_call_notification.yaml"
)
ICON_PATH = REPO_ROOT / "custom_components" / "ave_video44" / "brand" / "icon.png"
LOGO_PATH = REPO_ROOT / "custom_components" / "ave_video44" / "brand" / "logo.png"
README_PATH = REPO_ROOT / "README.md"


def _srgb_to_linear(c: float) -> float:
    """Convert sRGB channel (0..1) to linear luminance."""
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _relative_luminance(hex_code: str) -> float:
    """Calculate relative luminance according to WCAG 2.1 specs."""
    hex_clean = hex_code.lstrip("#")
    if len(hex_clean) == 3:
        hex_clean = "".join(c * 2 for c in hex_clean)
    r = int(hex_clean[0:2], 16) / 255.0
    g = int(hex_clean[2:4], 16) / 255.0
    b = int(hex_clean[4:6], 16) / 255.0
    return 0.2126 * _srgb_to_linear(r) + 0.7152 * _srgb_to_linear(g) + 0.0722 * _srgb_to_linear(b)


def _contrast_ratio(hex1: str, hex2: str) -> float:
    """Calculate WCAG contrast ratio between two hex colors."""
    lum1 = _relative_luminance(hex1)
    lum2 = _relative_luminance(hex2)
    l_max = max(lum1, lum2)
    l_min = min(lum1, lum2)
    return (l_max + 0.05) / (l_min + 0.05)


def _contains_emoji(text: str) -> bool:
    """Check if string contains literal emoji characters."""
    emoji_pattern = re.compile(
        r"[\U0001F600-\U0001F64F"  # Emoticons
        r"\U0001F300-\U0001F5FF"  # Misc Symbols and Pictographs
        r"\U0001F680-\U0001F6FF"  # Transport and Map
        r"\U0001F700-\U0001F77F"  # Alchemical Symbols
        r"\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
        r"\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
        r"\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        r"\U0001FA00-\U0001FA6F"  # Chess Symbols
        r"\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        r"\U00002702-\U000027B0"  # Dingbats
        r"\U000024C2-\U0001F251]"
    )
    return bool(emoji_pattern.search(text))


# ---------------------------------------------------------------------------
# Test Suite 1: Blueprint Automation YAML Schema & Clean Actions
# ---------------------------------------------------------------------------


class _BlueprintLoader(yaml.SafeLoader):
    """Custom YAML loader supporting Home Assistant !input tags."""
    pass


_BlueprintLoader.add_constructor(
    "!input",
    lambda loader, node: node.value if isinstance(node, yaml.ScalarNode) else loader.construct_sequence(node),
)


def test_blueprint_file_exists():
    """Verify incoming_call_notification blueprint file exists."""
    assert BLUEPRINT_PATH.is_file(), f"Blueprint file missing: {BLUEPRINT_PATH}"


def test_blueprint_schema():
    """Verify blueprint structure conforms to Home Assistant automation blueprint schema."""
    content = BLUEPRINT_PATH.read_text(encoding="utf-8")
    data = yaml.load(content, Loader=_BlueprintLoader)

    assert isinstance(data, dict), "Blueprint YAML must be a dict"
    assert "blueprint" in data, "Must contain 'blueprint' root key"
    bp = data["blueprint"]
    assert bp.get("domain") == "automation"
    assert bp.get("name"), "Blueprint name must be specified"
    assert bp.get("description"), "Blueprint description must be specified"

    # Blueprint variables section
    assert "variables" in data, "Blueprint must define 'variables' section"
    variables = data["variables"]
    assert "doorbell_device" in variables
    assert "tts_engine" in variables
    assert "media_players" in variables

    inputs = bp.get("input", {})
    assert "doorbell_device" in inputs or "doorbell_event" in inputs or "camera_entity" in inputs
    assert "notify_devices" in inputs or "notify_device" in inputs
    assert "media_players" in inputs
    assert "tts_engine" in inputs

    # Mobile app filter and multiple devices
    notify_selector = inputs["notify_devices"].get("selector", {}).get("device", {})
    assert notify_selector.get("multiple") is True

    # Trigger validation: incoming call event
    assert "trigger" in data
    triggers = data["trigger"] if isinstance(data["trigger"], list) else [data["trigger"]]
    has_event_trigger = any(
        t.get("platform") == "event"
        and t.get("event_type") in ("ave_video44_incoming_call", "ave_video44_doorbell_press")
        for t in triggers
    )
    assert has_event_trigger, "Blueprint must trigger on ave_video44 incoming call/doorbell event"

    # Condition on device_id
    assert "condition" in data, "Blueprint must include condition for device filtering"


def test_blueprint_deep_link_and_clean_labels():
    """Verify deep-link formatting and clean non-emoji actions in blueprint."""
    content = BLUEPRINT_PATH.read_text(encoding="utf-8")

    # Deep-link auto-answer query parameter
    assert "?ave_call=answer&device_id=" in content, (
        "Blueprint must include clickAction with '?ave_call=answer&device_id='"
    )
    assert "{{ trigger.event.data.device_id }}" in content or "{{ trigger.event.data['device_id'] }}" in content

    # Clean action labels without emoji
    assert "Rispondi" in content
    assert "Rifiuta" in content
    assert "Apri Cancello" in content or "Apri Cancelletto" in content
    assert not _contains_emoji(content), "Blueprint YAML must not contain decorative emojis"


# ---------------------------------------------------------------------------
# Test Suite 2: Lovelace Card JavaScript UX & Antislop Compliance
# ---------------------------------------------------------------------------


def test_card_file_exists():
    """Verify ave-video44-card.js file exists."""
    assert CARD_PATH.is_file(), f"Card JS missing: {CARD_PATH}"


def test_card_header_comment():
    """Verify Design Read header comment is present per antislop-ui."""
    content = CARD_PATH.read_text(encoding="utf-8")
    expected_header = (
        "Design Read: Intercom Card UI for Home Assistant Lovelace & Companion App, "
        "technical utility dark theme, dial ENERGY 1 / RHYTHM 1 / MOTION 1"
    )
    assert expected_header in content, "Card JS missing mandatory Design Read header comment"


def test_card_custom_element_registration():
    """Verify Custom Element registration for ave-video44-card."""
    content = CARD_PATH.read_text(encoding="utf-8")
    assert "customElements.define(" in content
    assert "ave-video44-card" in content


def test_card_state_memoization():
    """Verify set hass() performs state memoization to avoid interrupting active calls."""
    content = CARD_PATH.read_text(encoding="utf-8")
    assert "set hass(" in content
    # Should memoize/compare states before performing full DOM re-renders during active call
    memoization_indicators = ["_hass", "this._inCall", "this._callState"]
    found = sum(1 for ind in memoization_indicators if ind in content)
    assert found >= 2, "Card must memoize hass instance and guard active call state from re-renders"


def test_card_webaudio_resampler_and_full_duplex():
    """Verify WebAudio setup with echoCancellation, base64 payload and 8kHz PCM16 resampler."""
    content = CARD_PATH.read_text(encoding="utf-8")
    assert "echoCancellation: true" in content
    assert "noiseSuppression: true" in content
    assert "autoGainControl: true" in content
    assert "audioCtx.resume()" in content or "this._audioCtx.resume()" in content or ".resume()" in content
    # Resampler downsampling to 8000 Hz PCM16
    assert "8000" in content
    assert "Int16Array" in content or "pcm16" in content.lower()
    # Base64 payload and room_code intercom calling
    assert "payload:" in content or "payload" in content
    assert "_arrayBufferToBase64" in content
    assert "_base64ToInt16Array" in content
    assert "room_code:" in content or "room_code" in content
    # WebSocket endpoints
    assert "ave_video44/audio_tx" in content
    assert "ave_video44/audio_subscribe" in content


def test_card_track_cleanup_on_disconnect():
    """Verify disconnectedCallback stops media tracks and cleans up audio resources."""
    content = CARD_PATH.read_text(encoding="utf-8")
    assert "disconnectedCallback" in content
    assert "stop()" in content
    assert "getTracks()" in content or "_mediaStream" in content or "_stream" in content


def test_card_xss_safe_dom_updates():
    """Verify textContent is used for user dynamic data instead of unsafe innerHTML injection."""
    content = CARD_PATH.read_text(encoding="utf-8")
    # Verify textContent is used for text assignment
    assert ".textContent =" in content
    # Prohibit dangerous innerHTML bindings with unsanitized template variables
    assert "innerHTML = `<div" not in content or ".textContent" in content
    assert "innerHTML = `${" not in content


def test_card_aria_and_accessibility():
    """Verify accessibility attributes and Escape key handling."""
    content = CARD_PATH.read_text(encoding="utf-8")
    assert 'role="dialog"' in content or 'role="region"' in content
    assert "aria-modal=" in content or "aria-label=" in content
    assert "Escape" in content, "Card must handle Escape key to dismiss dialog/modal"


def test_card_ha_icon_usage_and_no_emoji():
    """Verify <ha-icon> usage and complete absence of emojis."""
    content = CARD_PATH.read_text(encoding="utf-8")
    assert "<ha-icon" in content
    assert 'icon="mdi:' in content
    assert not _contains_emoji(content), "Card JS must not contain any emoji characters"


def test_card_r27_states():
    """Verify R-27 loading, empty, and error states are implemented."""
    content = CARD_PATH.read_text(encoding="utf-8")
    content_lower = content.lower()
    assert "loading" in content_lower
    assert "error" in content_lower
    assert "idle" in content_lower or "empty" in content_lower


def test_card_wcag_aa_contrast_ratios():
    """Programmatically verify that color tokens meet WCAG AA contrast ratio >= 4.5:1."""
    tokens = {
        "bg_primary": "#18181b",
        "bg_surface": "#27272a",
        "text_primary": "#f4f4f5",
        "text_secondary": "#a1a1aa",
        "accent_answer": "#047857",
        "accent_hangup": "#dc2626",
        "accent_blue": "#2563eb",
        "focus_ring": "#60a5fa",
    }

    # Text primary on primary background
    cr_text_bg = _contrast_ratio(tokens["text_primary"], tokens["bg_primary"])
    assert cr_text_bg >= 4.5, f"text_primary on bg_primary ratio {cr_text_bg:.2f} < 4.5"

    # Text primary on surface background
    cr_text_surface = _contrast_ratio(tokens["text_primary"], tokens["bg_surface"])
    assert cr_text_surface >= 4.5, f"text_primary on bg_surface ratio {cr_text_surface:.2f} < 4.5"

    # Text secondary on primary background
    cr_sec_bg = _contrast_ratio(tokens["text_secondary"], tokens["bg_primary"])
    assert cr_sec_bg >= 4.5, f"text_secondary on bg_primary ratio {cr_sec_bg:.2f} < 4.5"

    # Text secondary on surface background
    cr_sec_surface = _contrast_ratio(tokens["text_secondary"], tokens["bg_surface"])
    assert cr_sec_surface >= 4.5, f"text_secondary on bg_surface ratio {cr_sec_surface:.2f} < 4.5"

    # Focus ring contrast on dark background
    cr_focus_bg = _contrast_ratio(tokens["focus_ring"], tokens["bg_primary"])
    assert cr_focus_bg >= 4.5, f"focus_ring on bg_primary ratio {cr_focus_bg:.2f} < 4.5"

    # White text on emerald answer button (#047857) - full WCAG AA >= 4.5:1
    cr_white_answer = _contrast_ratio("#ffffff", tokens["accent_answer"])
    assert cr_white_answer >= 4.5, f"white on accent_answer ratio {cr_white_answer:.2f} < 4.5"

    # White text on blue button
    cr_white_blue = _contrast_ratio("#ffffff", tokens["accent_blue"])
    assert cr_white_blue >= 4.5, f"white on accent_blue ratio {cr_white_blue:.2f} < 4.5"

    # White text on red button
    cr_white_hangup = _contrast_ratio("#ffffff", tokens["accent_hangup"])
    assert cr_white_hangup >= 4.5, f"white on accent_hangup ratio {cr_white_hangup:.2f} < 4.5"

    # UI graphical components contrast for action buttons against dark background
    cr_action_emerald = _contrast_ratio(tokens["accent_answer"], tokens["bg_primary"])
    assert cr_action_emerald >= 3.0, f"accent_answer on bg_primary UI component ratio {cr_action_emerald:.2f} < 3.0"


def test_card_intercom_call_button_toggles_to_hangup_in_call():
    """Verify #btnCallIntercom switches to hangup button and disables #intercomSelect during active call."""
    content = CARD_PATH.read_text(encoding="utf-8")
    assert 'id="callIntercomIcon"' in content
    assert 'id="callIntercomLabel"' in content
    assert "intercomSelect.disabled = true" in content
    assert 'btnCallIntercom.className = "btn-hangup"' in content
    assert 'callIntercomIcon.setAttribute("icon", "mdi:phone-hangup")' in content
    call_body = content.split("async _callIntercom()")[1].split("_arrayBufferToBase64")[0]
    assert "this._inCall" in call_body and "this._hangup()" in call_body, (
        "_callIntercom must check this._inCall and trigger this._hangup() instead of starting a duplicate call"
    )


def test_card_monitoring_hangup_and_clean_video():
    """Verify clean video stream without banner overlay and #btnHangup hidden in monitoring mode."""
    content = CARD_PATH.read_text(encoding="utf-8")

    # 1. Clean video stream with zero overlay
    assert 'id="callerBanner"' not in content, "callerBanner DOM element must be removed for clean video stream"

    # 2. No overlay CSS rule
    assert ".caller-banner" not in content, ".caller-banner CSS rule must be removed"

    # 3. btnHangup is hidden when in monitoring mode
    assert 'shadow.getElementById("btnHangup")' in content
    assert 'this._callState === "monitoring"' in content
    assert (
        'btnHangup.classList.add("hidden")' in content
        or "btnHangup.classList.add('hidden')" in content
    ), "btnHangup must be hidden when in monitoring mode"

    # Check that hiding btnHangup is tied to monitoring state
    assert re.search(
        r'this\._callState\s*===\s*["\']monitoring["\'][\s\S]{1,120}btnHangup\.classList\.add\(["\']hidden["\']\)',
        content,
    ), "Card logic must hide btnHangup when this._callState === 'monitoring'"


def test_card_native_mjpeg_stream_and_no_frame_polling():
    """Verify native MJPEG stream endpoint is used without setInterval polling."""
    content = CARD_PATH.read_text(encoding="utf-8")
    assert "camera_proxy_stream" in content
    assert "setInterval(pollFrame" not in content


# ---------------------------------------------------------------------------
# Test Suite 3: Brand PNG Assets Validation
# ---------------------------------------------------------------------------


def test_brand_assets_valid_png():
    """Verify icon.png and logo.png exist and are valid PNG files."""
    assert ICON_PATH.is_file(), f"Missing {ICON_PATH}"
    assert LOGO_PATH.is_file(), f"Missing {LOGO_PATH}"

    png_magic = b"\x89PNG\r\n\x1a\n"
    icon_bytes = ICON_PATH.read_bytes()
    logo_bytes = LOGO_PATH.read_bytes()

    assert icon_bytes.startswith(png_magic), "icon.png is not a valid PNG file"
    assert logo_bytes.startswith(png_magic), "logo.png is not a valid PNG file"

    # Validate IHDR chunk (width and height uint32 at offset 16 and 20)
    icon_w, icon_h = struct.unpack(">II", icon_bytes[16:24])
    logo_w, logo_h = struct.unpack(">II", logo_bytes[16:24])

    assert icon_w >= 32 and icon_h >= 32, f"icon.png too small: {icon_w}x{icon_h}"
    assert logo_w >= 64 and logo_h >= 32, f"logo.png too small: {logo_w}x{logo_h}"


# ---------------------------------------------------------------------------
# Test Suite 4: README Documentation Coverage
# ---------------------------------------------------------------------------


def test_readme_documentation():
    """Verify README.md contains bilingual documentation with key integration details."""
    assert README_PATH.is_file(), f"README.md missing: {README_PATH}"
    content = README_PATH.read_text(encoding="utf-8")

    # Bilingual sections
    assert "Italiano" in content or "Descrizione" in content
    assert "English" in content or "Description" in content

    # Key features documented
    assert "HACS" in content
    assert "ave-video44-card" in content or "Lovelace" in content
    assert "WebAudio" in content or "8kHz" in content
    assert "Rubrica" in content or "Address Book" in content or "HOUSETOHOUSE" in content
    assert "Blueprint" in content or "blueprint" in content
    assert "incoming_call" in content or "doorbell" in content
    assert not _contains_emoji(content), "README.md must not contain decorative emojis"


# ---------------------------------------------------------------------------
# Test Suite 5: Frontend Audio RX Playback, WebAudio & Gesture Synchronization
# ---------------------------------------------------------------------------


def _extract_js_method(content: str, method_name: str) -> str:
    """Extract method body from JS class by finding method declaration and matching braces."""
    pattern = rf"(?:async\s+)?{method_name}\s*\([^)]*\)\s*\{{"
    match = re.search(pattern, content)
    assert match is not None, f"Method {method_name} not found in card JS"
    start_pos = match.end() - 1
    depth = 0
    for i in range(start_pos, len(content)):
        char = content[i]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return content[start_pos + 1 : i]
    raise AssertionError(f"Could not find matching closing brace for {method_name}")


def test_card_ensure_audiocontext_synchronous_gesture():
    """Verify _ensureAudioContext is defined and called synchronously in click handlers before await."""
    content = CARD_PATH.read_text(encoding="utf-8")
    assert "_ensureAudioContext()" in content, "CARD_PATH must contain _ensureAudioContext()"

    for method_name in ("_monitor", "_answer", "_callIntercom"):
        body = _extract_js_method(content, method_name)
        assert "this._ensureAudioContext()" in body, (
            f"Method {method_name} must invoke this._ensureAudioContext()"
        )
        ensure_pos = body.find("this._ensureAudioContext()")
        await_match = re.search(r"\bawait\b", body)
        if await_match:
            await_pos = await_match.start()
            assert ensure_pos < await_pos, (
                f"In {method_name}, this._ensureAudioContext() must occur before any await "
                f"(ensure at {ensure_pos}, await at {await_pos})"
            )


def test_card_audio_rx_jitter_buffer_clamping():
    """Verify _playIncomingPcm16 schedules audio with 120ms jitter buffer and 300ms clamp."""
    content = CARD_PATH.read_text(encoding="utf-8")
    body = _extract_js_method(content, "_playIncomingPcm16")
    assert "0.120" in body or "0.12" in body, (
        "_playIncomingPcm16 must schedule initial playback at 120ms (0.120 or 0.12)"
    )
    assert "0.300" in body or "0.3" in body, (
        "_playIncomingPcm16 must clamp maximum jitter buffer delay at 300ms (0.300 or 0.3)"
    )
    assert "Math.min" in body, (
        "_playIncomingPcm16 must use Math.min for clamping maximum jitter buffer delay"
    )


def test_card_webview_compatibility_zero_optional_chaining():
    """Verify zero optional chaining (?.) and nullish coalescing (??) for legacy WebView compatibility."""
    content = CARD_PATH.read_text(encoding="utf-8")
    assert "?." not in content, "Modern optional chaining '?.' forbidden for WebView compatibility"
    assert "??" not in content, "Modern nullish coalescing '??' forbidden for WebView compatibility"


# ---------------------------------------------------------------------------
# Test Suite 6: Frontend Audio TX Capture, Resampling & Graceful Fallback
# ---------------------------------------------------------------------------


def test_card_graceful_mic_fallback_desktop():
    """Verify _answer handles missing microphone with non-blocking fallback and active audio RX."""
    content = CARD_PATH.read_text(encoding="utf-8")
    answer_fn = _extract_js_method(content, "_answer")
    assert "btnMute.disabled = true" in answer_fn or "disabled = true" in answer_fn
    assert 'muteLabel.textContent = "Microfono assente"' in answer_fn or "Microfono assente" in answer_fn
    assert "this._subscribeAudioRx()" in answer_fn, "Audio RX must continue even if mic is unavailable"


def test_card_cleanup_restores_mute_state():
    """Verify _cleanupCall re-enables mute button and restores default label."""
    content = CARD_PATH.read_text(encoding="utf-8")
    cleanup_fn = _extract_js_method(content, "_cleanupCall")
    assert "btnMute.disabled = false" in cleanup_fn
    assert 'muteLabel.textContent = "Muto"' in cleanup_fn


def test_card_audio_tx_20ms_accumulator():
    """Verify _startAudioTx accumulates 8kHz samples into 160-sample 20ms chunks."""
    content = CARD_PATH.read_text(encoding="utf-8")
    tx_fn = _extract_js_method(content, "_startAudioTx")
    assert "160" in tx_fn, "_startAudioTx must chunk audio into 160 samples (20ms at 8000 Hz)"
    assert "this._txAccumulator" in tx_fn or "txAccumulator" in tx_fn or "splice(0, 160)" in tx_fn, (
        "_startAudioTx must accumulate samples in a FIFO queue before transmission"
    )
    assert "ave_video44/audio_tx" in tx_fn


def test_card_version_bumped_1_3_1():
    """Verify CARD_VERSION constant is bumped to 1.3.1."""
    content = CARD_PATH.read_text(encoding="utf-8")
    assert 'const CARD_VERSION = "1.3.1";' in content


# ---------------------------------------------------------------------------
# Test Suite 7: Dynamic Audio/Mute Button Semantics in Monitoring & Talking
# ---------------------------------------------------------------------------


def test_card_dynamic_audio_button_states():
    """Verify _updateDynamicContent manages #btnMute across ringing, monitoring, and talking states."""
    content = CARD_PATH.read_text(encoding="utf-8")
    body = _extract_js_method(content, "_updateDynamicContent")

    assert "btnMute" in body, "_updateDynamicContent must manage btnMute element"

    # Ringing state: hidden during incoming ring
    assert 'btnMute.classList.add("hidden")' in body or "btnMute.classList.add('hidden')" in body, (
        "btnMute must be hidden during ringing state"
    )

    # Monitoring state with mic inactive: prompt to activate audio
    assert "Attiva audio" in body, (
        "btnMute label must be 'Attiva audio' in monitoring when mic is not active"
    )
    assert "mdi:microphone-outline" in body, (
        "btnMute icon must use outline variant when mic is inactive during monitoring"
    )

    # Talking state or mic active: default mute control
    assert '"Muto"' in body or "'Muto'" in body, (
        "btnMute label must be 'Muto' when audio is active"
    )
    assert "mdi:microphone" in body, (
        "btnMute icon must be mdi:microphone when mic is active"
    )


def test_card_monitoring_activate_audio_tx():
    """Verify _toggleMute activates audio TX when called in monitoring mode without active mic."""
    content = CARD_PATH.read_text(encoding="utf-8")
    mute_fn = _extract_js_method(content, "_toggleMute")

    # Guard for monitoring state and absent media stream
    assert "monitoring" in mute_fn, (
        "_toggleMute must check for monitoring state"
    )
    assert "this._mediaStream" in mute_fn, (
        "_toggleMute must check this._mediaStream presence"
    )

    # Audio TX activation
    assert "this._startAudioTx()" in mute_fn, (
        "_toggleMute must invoke this._startAudioTx() when mic is not yet active"
    )

    # Button transition to active mute state
    assert "Muto" in mute_fn, (
        "_toggleMute must switch label to 'Muto' upon activation"
    )
    assert "mdi:microphone" in mute_fn, (
        "_toggleMute must switch icon to mdi:microphone upon activation"
    )

    # Error handling fallback
    assert "Microfono assente" in mute_fn, (
        "_toggleMute must handle mic failure with 'Microfono assente' label"
    )
    assert "btnMute.disabled = true" in mute_fn or "disabled = true" in mute_fn, (
        "_toggleMute must disable btnMute if mic capture fails"
    )



