"""Dedicated pre-flight test suite mirroring all GitHub Actions CI/CD workflows (.github/workflows/*.yml)."""

import ast
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPONENT_DIR = ROOT / "custom_components" / "ave_video44"
WORKFLOWS_DIR = ROOT / ".github" / "workflows"


def test_workflow_validate_requirements_test_covers_all_imports():
    """Mirror validate.yml (tests job): every third-party import in codebase and tests must be in requirements_test.txt."""
    import_to_pkg = {
        "aiohttp": "aiohttp",
        "paho": "paho-mqtt",
        "yaml": "pyyaml",
        "cryptography": "cryptography",
        "voluptuous": "voluptuous",
        "pytest": "pytest",
        "pytest_asyncio": "pytest-asyncio",
    }
    ignored_roots = sys.stdlib_module_names | {
        "custom_components",
        "tests",
        "homeassistant",
        "haffmpeg",
        "conftest",
    }

    discovered_pkgs = set()
    for folder in (COMPONENT_DIR, ROOT / "tests"):
        for py_file in folder.rglob("*.py"):
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top = alias.name.split(".")[0]
                        if top not in ignored_roots:
                            assert top in import_to_pkg, (
                                f"Unmapped third-party import '{top}' in {py_file.relative_to(ROOT)}"
                            )
                            discovered_pkgs.add(import_to_pkg[top])
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    top = node.module.split(".")[0]
                    if top not in ignored_roots:
                        assert top in import_to_pkg, (
                            f"Unmapped third-party import '{top}' in {py_file.relative_to(ROOT)}"
                        )
                        discovered_pkgs.add(import_to_pkg[top])

    reqs_lines = [
        re.split(r"[><=~!]", line.strip())[0].strip().lower()
        for line in (ROOT / "requirements_test.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    for pkg in sorted(discovered_pkgs):
        assert pkg in reqs_lines, (
            f"Package '{pkg}' is imported but missing from requirements_test.txt; validate.yml will fail in CI"
        )


def test_workflow_validate_conftest_voluptuous_stub_validates_production_schemas():
    """Mirror validate.yml fallback: conftest._build_voluptuous_stub() must support all schema constructs in production."""
    from tests.conftest import _build_voluptuous_stub
    from custom_components.ave_video44.websocket_api import MAX_AUDIO_TX_B64_LEN

    stub = _build_voluptuous_stub()
    unlock_schema = stub.Schema(
        {
            stub.Optional("lock_id", default=1): stub.All(stub.Coerce(int), stub.In([1, 2])),
            stub.Optional("device_id"): str,
            stub.Optional("entity_id"): stub.Any(str, [str]),
        }
    )
    audio_tx_schema = stub.Schema(
        {
            stub.Required("id"): int,
            stub.Required("type"): "ave_video44/audio_tx",
            stub.Required("payload"): stub.All(str, stub.Length(min=1, max=MAX_AUDIO_TX_B64_LEN)),
            stub.Optional("session_id"): stub.All(str, stub.Length(min=1, max=128)),
        }
    )

    assert unlock_schema({"lock_id": "2"})["lock_id"] == 2
    with pytest.raises(stub.Invalid):
        unlock_schema({"lock_id": 9})

    assert audio_tx_schema({"id": 1, "type": "ave_video44/audio_tx", "payload": "AAAA"})["payload"] == "AAAA"
    with pytest.raises(stub.Invalid):
        audio_tx_schema({"id": 1, "type": "ave_video44/audio_tx", "payload": ""})
    with pytest.raises(stub.Invalid):
        audio_tx_schema({"id": 1, "type": "ave_video44/audio_tx", "payload": "A" * (MAX_AUDIO_TX_B64_LEN + 1)})


def test_workflow_validate_hassfest_and_hacs_contracts():
    """Mirror validate.yml (hassfest & hacs jobs): manifest key ordering, translations JSON, services.yaml parity."""
    manifest = json.loads((COMPONENT_DIR / "manifest.json").read_text(encoding="utf-8"))
    keys = list(manifest.keys())
    assert keys[0] == "domain" and keys[1] == "name"
    assert keys[2:] == sorted(keys[2:]), "Hassfest requires alphabetical keys after 'domain' and 'name'"

    for json_file in [
        ROOT / "hacs.json",
        COMPONENT_DIR / "manifest.json",
        COMPONENT_DIR / "icons.json",
        *list((COMPONENT_DIR / "translations").glob("*.json")),
    ]:
        data = json.loads(json_file.read_text(encoding="utf-8"))
        assert isinstance(data, dict) and data, f"Invalid or empty JSON in {json_file.relative_to(ROOT)}"

    services_yaml = yaml.safe_load((COMPONENT_DIR / "services.yaml").read_text(encoding="utf-8"))
    for svc in ("unlock", "call_intercom", "answer_call", "hangup_call"):
        assert svc in services_yaml, f"Service '{svc}' registered in __init__.py is missing from services.yaml"


def test_workflow_release_version_and_changelog_extraction():
    """Mirror release.yml: verify version parity across all 4 files and non-empty CHANGELOG.md section for v{version}."""
    manifest = json.loads((COMPONENT_DIR / "manifest.json").read_text(encoding="utf-8"))
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    card_js = (COMPONENT_DIR / "frontend" / "ave-video44-card.js").read_text(encoding="utf-8")
    from custom_components.ave_video44 import _CARD_VERSION

    ver = manifest["version"]
    assert pyproject["project"]["version"] == ver, "pyproject.toml version does not match manifest.json"
    assert _CARD_VERSION == ver, "__init__.py _CARD_VERSION does not match manifest.json"
    card_match = re.search(r'const\s+CARD_VERSION\s*=\s*"([^"]+)"', card_js)
    assert card_match and card_match.group(1) == ver, "ave-video44-card.js CARD_VERSION does not match manifest.json"

    # Exact extraction logic from .github/workflows/release.yml lines 32-47
    tag = f"v{ver}"
    header = f"## {tag} "
    lines = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    out, in_sec = [], False
    for line in lines:
        if line.startswith(header):
            in_sec = True
            continue
        if in_sec and line.startswith("## "):
            break
        if in_sec:
            out.append(line)
    notes = "\n".join(out).strip()
    assert notes, f"release.yml will fail: empty or missing '{header}— YYYY-MM-DD' section in CHANGELOG.md"
    assert "### 🇬🇧 English" in notes, f"Missing English section in CHANGELOG.md for {tag}"
    assert "### 🇮🇹 Italiano" in notes, f"Missing Italian section in CHANGELOG.md for {tag}"


def test_workflow_card_sanity_syntax_and_webview_guard():
    """Mirror card.yml: run node --check and verify no optional chaining (?.) or nullish coalescing (??)."""
    card_path = COMPONENT_DIR / "frontend" / "ave-video44-card.js"
    card_js = card_path.read_text(encoding="utf-8")

    code = re.sub(r"/\*[\s\S]*?\*/", "", card_js)
    code = re.sub(r"^\s*//.*$", "", code, flags=re.MULTILINE)
    match = re.search(r"\?\.[A-Za-z0-9_$([]|\?\?", code)
    assert match is None, f"card.yml will fail: forbidden operator '{match.group(0)}' in ave-video44-card.js"

    node_bin = shutil.which("node")
    if node_bin:
        res = subprocess.run([node_bin, "--check", str(card_path)], capture_output=True, text=True, check=False)
        assert res.returncode == 0, f"card.yml node --check failed:\n{res.stderr}"
