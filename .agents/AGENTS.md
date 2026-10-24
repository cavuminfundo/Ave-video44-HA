# Workspace Agent Router — AVE Video V44

> **AVE Video V44** (`custom_components/ave_video44`) is a Home Assistant custom integration and async Python client for **AVE Video V44** video intercom systems (**V44 EASY**, **V44 SMART**, `VI2F-PIT7WF`, `TS-SMART7xx`, `TS-SMART10xx`, and GVS outdoor doorstations).

---

## 📖 [ALL AGENTS] Repository Documentation Index
Before starting any work, consult the relevant documentation files below:
- **Global Agent Guidelines & Safety:** Refer to `~/.gemini/config/AGENTS.md` for global execution rules.
- **System Architecture & Component Model:** Read [docs/architecture.md](file:///./docs/architecture.md).
- **Project Roadmap & Evolution Phases:** Read [docs/roadmap.md](file:///./docs/roadmap.md).
- **Low-Level Code Implementation & Security Bible:** Read [docs/code-implementation.md](file:///./docs/code-implementation.md).
- **Lessons Learned & Discovered Hardware Invariants:** Read [.agents/memory/lessons.md](file:///./.agents/memory/lessons.md).

---

## 🧭 [ALL AGENTS] Golden Rules & Engineering Principles

### 1. Ponytail Ladder (Anti-Overengineering)
Stop at the first rung that holds:
1. **Does this need to exist at all?** Speculative need = skip it (YAGNI).
2. **Already in this codebase?** Reuse existing helpers, types, and constants.
3. **Stdlib does it?** Use Python standard library (`asyncio`, `dataclasses`, `enum`, `json`, `hashlib`, `hmac`, `struct`).
4. **Native platform feature covers it?** Use Home Assistant core helpers (`DataUpdateCoordinator`, `CoordinatorEntity`, `async_get_clientsession`, `ConfigEntryAuthFailed`, `websocket_api`).
5. **Already-installed dependency solves it?** Use `aiohttp` or existing HA dependencies. Never add external wheels without strict evaluation.
6. **Can it be one line?** One line.
7. **Only then:** The minimum code that works.

Code first. Then at most three short lines: what was skipped, when to add it. No unrequested abstractions, no speculative generic intercom factory classes.

### 2. Antislop Comment Hygiene
- Modify comments only when working on code; never add decorative banners, box drawings, or ALL CAPS headers.
- Eliminate restating the obvious (`// Initialize coordinator` above coordinator setup).
- Eliminate step-by-step workflow narration (`// Step 1: get token`, `// Step 2: call endpoint`).
- Eliminate decorative emojis in comments and log strings.
- Keep comments strictly focused on non-obvious invariants: why, protocol framing, hardware timing, audio resampling. Maximum 1-2 lines per comment.

### 3. Zero Plaintext Secrets Policy
- **Never commit credentials**: passwords, session IDs, app secrets, HMAC keys, SIP passwords, or RTSP tokens must NEVER be hardcoded or checked into Git.
- **No plaintext `.env` in production**: Integration runtime configuration must be managed through Home Assistant `ConfigEntry` encrypted storage (`config_flow.py`).
- **Strict redaction in logs & diagnostics**: All session IDs, bearer tokens, passwords, app secrets, and personal identifiers must be masked before writing diagnostics (`diagnostics.py`) or emitting debug logs.

### 4. Schema-Driven Development (SDD)
- All external API request/response payloads and local binary protocol packets (`GVSGVS\xa5\xa5\xa5\xa5`) must be documented and typed using typed dataclasses or pydantic/msgspec models before writing entity bindings.
- Validate boundaries gracefully: handle network drops, packet loss, and missing fields without crashing the coordinator or terminating active audio streams.

### 5. Mandatory Release, Versioning & Changelog Policy (Mandatory on Commit & Push)
Ad ogni `git commit` e `git push` su `main`, l'agente DEVE:
1. Incrementare la versione SemVer (`patch` per fix/asset/refactoring, `minor` per nuove feature/entità) in modo sincronizzato in:
   - `custom_components/ave_video44/manifest.json` (`"version": "X.Y.Z"`)
   - `pyproject.toml` (`version = "X.Y.Z"`)
   - `custom_components/ave_video44/frontend/ave-video44-card.js` (`const CARD_VERSION = "X.Y.Z";`)
2. Compilare le note di rilascio in `CHANGELOG.md` subito sotto `## [Non rilasciato]` aggiungendo l'intestazione `## vX.Y.Z — YYYY-MM-DD` (con sezioni `### 🇬🇧 English` e `### 🇮🇹 Italiano`).
3. Creare e pushare il tag Git corrispondente (`git tag -f vX.Y.Z && git push -f origin vX.Y.Z`) oltre a `origin/main`. Il push del tag attiva automaticamente `.github/workflows/release.yml` che estrae la sezione corrispondente da `CHANGELOG.md` (tramite `header = f"## {tag} "`) e pubblica/aggiorna la GitHub Release con le relative note bilingue.

---

## 🧪 [ALL AGENTS] Mandatory Quality Gates
Automated verification standards for all changes:
- **Host Test Runner**: Python tests are run via `uv run --with pytest pytest -q --tb=short --maxfail=2` (or `.venv/bin/pytest`).
- **Code Style & Linting**: Run `uv run ruff check custom_components/ tests/` and `uv run ruff format --check custom_components/ tests/`.
- **🚫 Sub-Agents Test Ban**: Sub-Agents are strictly forbidden from executing global test suites. Only the Master Agent executes test runners.
- **🚫 No Task Polling**: Do NOT run polling loops or timer schedules (`schedule`) while waiting for tests or commands.

---

## 🏗️ [ALL AGENTS] Architectural Standards
- **Stack**: Python >=3.12, Home Assistant Core integration ecosystem, `aiohttp` async networking.
- **Async Safety**: Every I/O operation must be non-blocking and execute on the event loop with timeouts (`asyncio.timeout(10.0)`).
- **Session Lifecycle**: Always reuse Home Assistant's managed `aiohttp.ClientSession` via `async_get_clientsession(hass)`. Never instantiate unmanaged `ClientSession` objects.
- **Audio Resampling Invariants**:
  - WebAudio frontend captures microphone input (44.1kHz or 48kHz) and downsamples to 8000 Hz mono 16-bit PCM (PCM16 little-endian).
  - Transmitted via Home Assistant WebSocket binary frames (`ave_video44/audio_tx`).
  - Backend transcode between PCM16 and G.711a (PCMA) for RTP UDP streams on port 8302.
- **Intercom Routing & Lock Timing**:
  - Inter-apartment calls use local HOUSETOHOUSE SIP routing without cloud dependencies.
  - Relays trigger with automatic relock after `unlock_pulse_duration` seconds (default: 2s).
