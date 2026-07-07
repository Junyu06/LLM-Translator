# Startup Performance and Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove avoidable startup-time bridge work, make startup phases observable, and surface Windows hotkey listener status without blocking first paint.

**Architecture:** Keep health/config paths on lightweight Rust and Python code paths, while translation/OCR/hotkey features load heavy modules only when invoked. Add timestamped startup diagnostics in Rust and Python using stderr plus an opt-in log file. Let React render immediately from local defaults/Rust config, then update a backend status indicator after asynchronous health checks complete.

**Tech Stack:** Python 3.14 `unittest`; React 18 + TypeScript + Vite; Tauri 2 Rust shell; no new runtime dependencies.

## Global Constraints

- Keep Windows release bridge packaging one-dir; do not switch to PyInstaller one-file mode.
- `health`, `get-config`, `save-config`, and hotkey paths must not import `python_backend.services.translation_service`.
- Startup diagnostics must write to stderr and optionally to a log file when enabled.
- Production Windows bridge resolution must use packaged resource/app paths only; source-tree fallback is allowed only in debug builds.
- UI first paint must not wait up to 12 seconds for `waitForBackend()`.
- Windows hotkey listener starts after `frontend_ready` asynchronously; failures are stored in queryable status and visible in the UI status line.
- Use TDD for code behavior changes where the repo has test harness coverage. For Rust/UI surfaces without a dedicated unit-test harness, capture reproducible validation with `cargo check` and `npm run build:frontend`.

---

## File Map

- `python_backend/bridge.py`: lazy import translation service, Python startup diagnostics.
- `tests/test_bridge_startup.py`: import regression tests proving health/config do not import translation service and logging is opt-in.
- `src-tauri/src/main.rs`: Rust startup diagnostics, production bridge fallback guard, hotkey status storage, deferred Windows listener startup.
- `src/lib/api.ts`: replace blocking `waitForBackend()` startup helper with immediate config load and async health/status refresh helpers.
- `src/App.tsx`: render immediately, show backend/hotkey status, call `frontend_ready` before async backend health settles.
- `docs/plans/2026-07-07-fix-1-startup-performance.md`: this plan.

## Task 1: Python Bridge Lazy Import and Diagnostics

**Files:**
- Modify: `python_backend/bridge.py`
- Create: `tests/test_bridge_startup.py`

**Interfaces:**
- Produces: `startup_log(stage: str, details: str | None = None) -> None`
- Produces: `get_translation_types() -> tuple[type, type]`
- Produces: `get_translation_service() -> Any`

- [ ] **Step 1: Write failing import regression tests**

Create `tests/test_bridge_startup.py` with tests that run the bridge in a subprocess and assert `python_backend.services.translation_service` is absent from `-X importtime` output for `health`, `get-config`, and `save-config`. Include a positive control asserting `translate` still reaches the translation path when fed a minimal invalid/non-empty request.

Run:

```bash
python3 -m unittest tests.test_bridge_startup -v
```

Expected before implementation: at least the health import test fails because `translation_service` appears in import-time output.

- [ ] **Step 2: Move translation imports behind helpers**

Remove top-level `TranslationService` and `TranslationRequest` imports from `python_backend/bridge.py`. Import `TranslationRequest` and `TranslationService` inside helpers used only by `cmd_translate()` and `cmd_translate_stream()`.

- [ ] **Step 3: Add lightweight diagnostics**

Add `startup_log()` that writes ISO-8601 UTC stage messages to stderr when `TRANSLATOR_STARTUP_LOG=1`, and also appends to `TRANSLATOR_STARTUP_LOG_FILE` when that variable is set. Log Python bridge import completion and command dispatch start.

- [ ] **Step 4: Verify red-to-green**

Run:

```bash
python3 -m unittest tests.test_bridge_startup -v
python3 -X importtime python_backend/bridge.py health 2>&1 | grep -c "translation_service"
python3 python_backend/bridge.py health
```

Expected after implementation: tests pass, grep count is `0`, health prints JSON with `"status": "ok"`.

## Task 2: Rust Startup Diagnostics, Bridge Fallback, and Hotkey Status

**Files:**
- Modify: `src-tauri/src/main.rs`

**Interfaces:**
- Produces: `startup_log(stage: &str, details: Option<&str>)`
- Produces: `HotkeyStatus { state: String, error: Option<String> }`
- Produces command: `hotkey_status() -> HotkeyStatus`

- [ ] **Step 1: Add Rust diagnostics primitives**

Add `startup_log()` using `SystemTime`/UNIX milliseconds to write `translator-startup stage=<stage>` to stderr. If `TRANSLATOR_STARTUP_LOG_FILE` is set, append the same line to that file.

- [ ] **Step 2: Instrument required startup phases**

Log app main start, setup start/end, window ready, `frontend_ready`, and bridge spawn start/end in `run_bridge()` and streaming bridge spawn. Use command names in details.

- [ ] **Step 3: Guard packaged bridge fallback**

Refactor `bridge_process()` so Windows release builds return a clear error when packaged bridge resource lookup fails. Keep Python source fallback only under `debug_assertions` or non-Windows development paths.

- [ ] **Step 4: Defer Windows hotkey listener**

Remove setup-time Windows listener start. In `frontend_ready`, after marking the frontend ready and flushing pending clipboard triggers, spawn a background thread that calls `spawn_hotkey_listener()` and records success/failure in `AppState.hotkey_status`.

- [ ] **Step 5: Expose hotkey status**

Add `HotkeyStatus` to state, initialize it as `unknown`, update it to `running`, `disabled`, or `error`, and expose `hotkey_status` through Tauri `invoke_handler`.

- [ ] **Step 6: Verify Rust build surface**

Run:

```bash
~/.cargo/bin/cargo check --manifest-path src-tauri/Cargo.toml
```

Expected: command exits 0.

## Task 3: Non-Blocking React Startup and Status Indicator

**Files:**
- Modify: `src/lib/api.ts`
- Modify: `src/App.tsx`

**Interfaces:**
- Produces: `loadInitialConfig(): Promise<{ config: AppConfig; desktopStatus: DesktopBackendStatus | null }>`
- Produces: `refreshBackendStatus(): Promise<DesktopBackendStatus | null>`
- Produces: `getHotkeyStatus(): Promise<{ state: string; error: string | null } | null>`

- [ ] **Step 1: Replace blocking startup helper**

Keep `waitForBackend()` only for explicit callers if needed, but add `loadInitialConfig()` that reads config without polling health. In Tauri, `getConfig()` already stays Rust-side; in browser mode, use `/config`.

- [ ] **Step 2: Render immediately**

In `App.tsx`, replace mount-time `waitForBackend().then(...)` with `loadInitialConfig().then(...)`, set local UI ready as soon as config loads or defaults are used, and call `notifyFrontendReady()` immediately in Tauri runtime.

- [ ] **Step 3: Add non-blocking backend/hotkey status refresh**

After first render, call `refreshBackendStatus()` and `getHotkeyStatus()` asynchronously. Show backend state and hotkey errors in the existing footer/status text without blocking input, settings, history, or translate button rendering.

- [ ] **Step 4: Verify frontend build**

Run:

```bash
/opt/homebrew/bin/npm run build:frontend
```

Expected: TypeScript and Vite build exit 0.

## Task 4: Final Validation and Solo Repo Merge

**Files:**
- No new source files unless validation finds a fix required.

- [ ] **Step 1: Run full required validation**

Run exactly:

```bash
python3 -m unittest discover -s tests -v
python3 -X importtime python_backend/bridge.py health 2>&1 | grep -c "translation_service"
python3 python_backend/bridge.py health
/opt/homebrew/bin/npm run build:frontend
~/.cargo/bin/cargo check --manifest-path src-tauri/Cargo.toml
git log --oneline -3
```

- [ ] **Step 2: Commit and merge**

Commit all implementation changes on `worker/2026-07-07-fix-1-startup-performance`. If validation is green, merge to `main` and push `main` because this is a solo repo with no contrary AGENTS rule.
