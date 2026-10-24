"""Governance and repository sanity tests for Ave-video44-HA."""

import json
from pathlib import Path
import re
import tomllib

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
