"""Governance and repository sanity tests for Ave-video44-HA."""

import json
from pathlib import Path
import re
import tomllib
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_manifest_hassfest_and_repo_urls():
    manifest_path = ROOT / "custom_components" / "ave_video44" / "manifest.json"
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    keys = list(raw.keys())
    assert keys[0] == "domain"
    assert keys[1] == "name"
    assert keys[2:] == sorted(keys[2:]), "Hassfest requires alphabetical keys after domain and name"
    assert raw["codeowners"] == ["@cavuminfundo"]
    assert raw["documentation"] == "https://github.com/cavuminfundo/Ave-video44-HA"
    assert raw["issue_tracker"] == "https://github.com/cavuminfundo/Ave-video44-HA/issues"
    assert raw.get("dependencies") == ["ffmpeg", "http"]


def test_license_file_present():
    license_path = ROOT / "LICENSE"
    assert license_path.is_file(), "Missing LICENSE file in repository root"
    assert "MIT License" in license_path.read_text(encoding="utf-8")


def test_hacs_json_manifest():
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    assert hacs.get("content_in_root") is False
    assert "zip_release" not in hacs
    assert hacs.get("render_readme") is True


def test_semver_parity_across_manifest_pyproject_and_card():
    manifest = json.loads((ROOT / "custom_components" / "ave_video44" / "manifest.json").read_text(encoding="utf-8"))
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    card_js = (ROOT / "custom_components" / "ave_video44" / "frontend" / "ave-video44-card.js").read_text(encoding="utf-8")

    version = manifest["version"]
    assert pyproject["project"]["version"] == version
    match = re.search(r'const\s+CARD_VERSION\s*=\s*"([^"]+)"', card_js)
    assert match is not None, "CARD_VERSION constant missing in ave-video44-card.js"
    assert match.group(1) == version


def test_card_legacy_webview_compatibility():
    card_js = (ROOT / "custom_components" / "ave_video44" / "frontend" / "ave-video44-card.js").read_text(encoding="utf-8")
    code = re.sub(r"/\*[\s\S]*?\*/", "", card_js)
    code = re.sub(r"^\s*//.*$", "", code, flags=re.MULTILINE)
    match = re.search(r"\?\.[A-Za-z0-9_$([]|\?\?", code)
    assert match is None, f"Found WebView-incompatible operator '{match.group(0) if match else ''}' in ave-video44-card.js"


def test_github_workflows_and_gitignore_present():
    for wf in ("validate.yml", "release.yml", "card.yml", "version-guard.yml", "pip-audit.yml"):
        wf_path = ROOT / ".github" / "workflows" / wf
        assert wf_path.is_file(), f"Missing workflow {wf}"
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in (".codegraph/", "graphify-out/", "*.egg-info/", "uv.lock", ".venv/", ".pytest_cache/", ".env"):
        assert pattern in gitignore
    reqs = (ROOT / "requirements_test.txt").read_text(encoding="utf-8")
    assert "pyyaml" in reqs.lower()


def test_icons_json_and_translation_keys():
    icons_path = ROOT / "custom_components" / "ave_video44" / "icons.json"
    assert icons_path.is_file(), "icons.json missing"
    raw = json.loads(icons_path.read_text(encoding="utf-8"))
    assert "entity" in raw, "icons.json missing top-level 'entity' key"
    entity_dict = raw["entity"]

    platforms = list(entity_dict.keys())
    expected_platforms = ["binary_sensor", "button", "camera", "event", "lock", "select", "sensor"]
    assert platforms == expected_platforms, f"Platforms not strictly sorted or missing: {platforms}"

    en_trans = json.loads((ROOT / "custom_components" / "ave_video44" / "translations" / "en.json").read_text(encoding="utf-8"))
    en_entity = en_trans.get("entity", {})

    for platform, keys_dict in entity_dict.items():
        keys = list(keys_dict.keys())
        assert keys == sorted(keys), f"Translation keys for platform '{platform}' not alphabetically sorted"
        assert platform in en_entity, f"Platform '{platform}' missing from translations/en.json"
        assert set(keys) == set(en_entity[platform].keys()), f"Keys mismatch for platform '{platform}' between icons.json and en.json"
        for entity_key, icon_data in keys_dict.items():
            default_icon = icon_data.get("default", "")
            assert default_icon.startswith("mdi:"), f"Icon '{default_icon}' for {platform}.{entity_key} must start with 'mdi:'"

    manifest = json.loads((ROOT / "custom_components" / "ave_video44" / "manifest.json").read_text(encoding="utf-8"))
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    card_js = (ROOT / "custom_components" / "ave_video44" / "frontend" / "ave-video44-card.js").read_text(encoding="utf-8")

    assert manifest["version"] == "1.2.3"
    assert pyproject["project"]["version"] == "1.2.3"
    match = re.search(r'const\s+CARD_VERSION\s*=\s*"([^"]+)"', card_js)
    assert match is not None
    assert match.group(1) == "1.2.3"


def test_card_editor_and_zero_yaml_support():
    card_js = (ROOT / "custom_components" / "ave_video44" / "frontend" / "ave-video44-card.js").read_text(encoding="utf-8")
    assert 'customElements.define("ave-video44-card-editor"' in card_js or "class AveVideo44CardEditor" in card_js
    assert "getConfigElement" in card_js
    assert "getStubConfig" in card_js
    assert "_autoResolveEntities" in card_js
    # Ensure no direct user interpolation into innerHTML in editor
    editor_match = re.search(r"class AveVideo44CardEditor[\s\S]*?customElements\.define", card_js)
    assert editor_match is not None, "AveVideo44CardEditor missing in card script"
    editor_code = editor_match.group(0)
    assert "${this._config" not in editor_code, "Prevent DOM XSS: do not interpolate config values directly into innerHTML"


def test_card_bubble_styling_retry_and_title():
    """Verify Bubble Card pill styling, retry timer, hidden live video, and title support."""
    card_js = (ROOT / "custom_components" / "ave_video44" / "frontend" / "ave-video44-card.js").read_text(encoding="utf-8")
    assert 'CARD_VERSION = "1.2.3"' in card_js or "CARD_VERSION = '1.2.3'" in card_js
    assert "border-radius: 28px" in card_js
    assert ".btn-icon-bubble" in card_js
    assert "max-width: 780px" in card_js
    assert 'liveVideo.classList.add("hidden")' in card_js
    assert "cameraStreamImg" in card_js and "onerror" in card_js
    assert 'data-field="title"' in card_js
    assert "isVideoActive && cameraEntity" in card_js
    assert "hangupLabel" in card_js
    assert "_expandMasonryColumn" in card_js
    assert "ll-rebuild" in card_js
    assert "?." not in card_js, "Optional chaining ?. forbidden for WebView compatibility"
    assert "??" not in card_js, "Nullish coalescing ?? forbidden for WebView compatibility"
    assert "${this._config" not in card_js



def test_init_add_extra_js_url():
    init_py = (ROOT / "custom_components" / "ave_video44" / "__init__.py").read_text(encoding="utf-8")
    assert "add_extra_js_url" in init_py
    assert "/ave_video44_card/ave-video44-card.js?v=1.2.3" in init_py



def test_official_brand_suite_8_files():
    brand_dir = ROOT / "custom_components" / "ave_video44" / "brand"
    required = [
        "icon.png",
        "icon@2x.png",
        "dark_icon.png",
        "dark_icon@2x.png",
        "logo.png",
        "logo@2x.png",
        "dark_logo.png",
        "dark_logo@2x.png",
    ]
    for filename in required:
        file_path = brand_dir / filename
        assert file_path.is_file(), f"Missing brand file {filename}"
        data = file_path.read_bytes()
        assert data.startswith(b"\x89PNG\r\n\x1a\n"), f"{filename} is not a valid PNG"
        assert len(data) > 4096, f"{filename} size is too small ({len(data)} <= 4096)"


def test_diagnostics_redaction():
    from custom_components.ave_video44.diagnostics import TO_REDACT, async_redact_data
    for sensitive_key in ("session_id", "sessionId", "jsessionid", "otp", "password", "token"):
        assert sensitive_key in TO_REDACT, f"Key {sensitive_key} missing from TO_REDACT"
    sample = {
        "session_id": "secret_sess",
        "jsessionid": "secret_cookie",
        "otp": "123456",
        "safe_key": "safe_val",
    }
    redacted = async_redact_data(sample)
    assert redacted["session_id"] == "**REDACTED**"
    assert redacted["jsessionid"] == "**REDACTED**"
    assert redacted["otp"] == "**REDACTED**"
    assert redacted["safe_key"] == "safe_val"


def test_card_idempotent_guards():
    """Verify customElements.define and customCards have idempotency guards and monitor button."""
    card_js = (ROOT / "custom_components" / "ave_video44" / "frontend" / "ave-video44-card.js").read_text(encoding="utf-8")
    assert 'customElements.get("ave-video44-card")' in card_js
    assert 'customElements.get("ave-video44-card-editor")' in card_js
    assert "window.customCards.some(" in card_js
    assert "btnMonitor" in card_js or "_monitor" in card_js


@pytest.mark.asyncio
async def test_async_register_card_registers_lovelace_resource():
    """Verify _async_register_card registers resource in Lovelace storage and domain data."""
    from unittest.mock import AsyncMock, MagicMock
    from custom_components.ave_video44 import _async_register_card, DOMAIN

    class FakeResources:
        def __init__(self):
            self.loaded = True
            self.items = []

        def async_items(self):
            return list(self.items)

        async def async_create_item(self, item):
            self.items.append(dict(item, id="res_1"))

        async def async_update_item(self, item_id, item):
            for i, it in enumerate(self.items):
                if it.get("id") == item_id:
                    self.items[i] = dict(item, id=item_id)

    class FakeLovelace:
        def __init__(self):
            self.resources = FakeResources()

    hass = MagicMock()
    hass.data = {
        "lovelace": FakeLovelace(),
        DOMAIN: {},
    }
    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()

    await _async_register_card(hass)

    items = hass.data["lovelace"].resources.async_items()
    assert len(items) == 1
    assert items[0]["url"] == "/ave_video44_card/ave-video44-card.js?v=1.2.3"
    assert items[0]["res_type"] == "module"
    assert hass.data[DOMAIN]["card_registered"] is True



