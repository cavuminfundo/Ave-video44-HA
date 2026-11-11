import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
INIT_PY = REPO_ROOT / "custom_components" / "ave_video44" / "__init__.py"
MANIFEST_JSON = REPO_ROOT / "custom_components" / "ave_video44" / "manifest.json"
PYPROJECT_TOML = REPO_ROOT / "pyproject.toml"


def test_semver_sync_1_3_9():
    """Verify version 1.3.9 synchronization across backend files."""
    init_content = INIT_PY.read_text(encoding="utf-8")
    manifest_content = MANIFEST_JSON.read_text(encoding="utf-8")
    pyproject_content = PYPROJECT_TOML.read_text(encoding="utf-8")

    assert '_CARD_VERSION = "1.3.9"' in init_content
    assert 'resource_url = f"{_CARD_URL}?v={_CARD_VERSION}"' in init_content
    assert '"version": "1.3.9"' in manifest_content
    assert 'version = "1.3.9"' in pyproject_content


test_semver_sync_1_3_8 = test_semver_sync_1_3_9


def test_static_paths_cache_headers_disabled():
    """Verify cache_headers=False on card bundles to avoid WebView 31-day cache lock."""
    content = INIT_PY.read_text(encoding="utf-8")
    card_cfg = re.search(
        r"StaticPathConfig\([^)]*url_path=_CARD_URL[^)]*cache_headers=False",
        content,
        re.DOTALL,
    ) or re.search(
        r"StaticPathConfig\(.*?url_path=_CARD_URL.*?cache_headers=False",
        content,
        re.DOTALL,
    )
    legacy_cfg = re.search(
        r"StaticPathConfig\([^)]*url_path=_LEGACY_CARD_URL[^)]*cache_headers=False",
        content,
        re.DOTALL,
    ) or re.search(
        r"StaticPathConfig\(.*?url_path=_LEGACY_CARD_URL.*?cache_headers=False",
        content,
        re.DOTALL,
    )
    assert card_cfg is not None, "_CARD_URL must configure cache_headers=False"
    assert legacy_cfg is not None, "_LEGACY_CARD_URL must configure cache_headers=False"
