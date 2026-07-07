# Error Handling and Frontend Resilience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make backend failures structured and recoverable, make malformed API/config input return clear errors, and prevent frontend storage/polling/status races from breaking the UI.

**Architecture:** Extend the existing backend error classes with stable codes and map Ollama/local/HTTP failures into those codes at the source. Keep service streaming alive until an error event can describe the failed segment, while synchronous translate still raises for API callers. On the frontend, isolate localStorage parsing into guarded helpers, use a synchronous in-flight ref before async work starts, make stream polling cleanup deterministic, and guard delayed copy status updates with a timeout/version ref.

**Tech Stack:** Python 3.14 `unittest`; React 18 + TypeScript + Vite; no new runtime dependencies.

## Global Constraints

- Use TDD for Python behavior changes: write the failing unittest first, run it red, implement, then run it green.
- Backend error codes must be stable strings for model missing, Ollama unavailable, timeout, JSON decode failure, dependency missing, and unexpected backend response.
- `python_backend/api_server.py` must return JSON 400 for `ValueError` and `TypeError` from malformed translate/config payloads.
- Corrupt config files must keep the default fallback behavior, emit a stderr diagnostic, and back up the corrupt file with a `.corrupt` suffix before returning defaults.
- Frontend history/config localStorage corruption must not crash first render; bad values move to backup keys and the app starts with defaults.
- Stream polling failure must clear `isSubmitting` and `currentJobIdRef`, set a user-visible status, and allow a new submit.
- Double-trigger prevention must use a synchronous ref set before any async work.
- Copy-success delayed status must not overwrite a newer status.

---

## File Map

- `backend/errors.py`: add stable `code` support to backend exceptions.
- `backend/ollama_backend.py`: map local/HTTP timeout, JSON decode, dependency, missing-model, unreachable, and unexpected-response cases.
- `python_backend/services/translation_service.py`: emit structured segment error events and re-raise in synchronous `translate()`.
- `python_backend/api_server.py`: catch `TypeError` alongside `ValueError`.
- `python_backend/config.py`: stderr diagnostic and `.corrupt` backup for unreadable config.
- `python_backend/models.py`: no planned changes for this task unless tests expose request construction behavior.
- `tests/test_backend_errors.py`: focused backend error-code tests.
- `tests/test_translation_service.py`: service-level segment error event test.
- `tests/test_api_server.py`: malformed payload JSON 400 tests.
- `tests/test_config_store.py`: corrupt config backup/diagnostic test.
- `src/App.tsx`: guarded localStorage, in-flight ref, polling cleanup, copy status guard.
- `src/styles.css`: `.progress-container` dimensions/positioning.

## Task 1: Backend Error Codes and Stream Error Events

**Files:**
- Modify: `backend/errors.py`
- Modify: `backend/ollama_backend.py`
- Modify: `python_backend/services/translation_service.py`
- Create: `tests/test_backend_errors.py`
- Modify: `tests/test_translation_service.py`

**Interfaces:**
- `BackendError(message: str = "", code: str = "backend_error")`
- Subclass defaults: `BackendUnavailableError.code == "ollama_unavailable"`, `BackendRequestError.code == "backend_request_failed"`, `ModelNotFoundError.code == "model_not_found"`.
- Service error event shape: `{"event": "error", "code": exc.code, "message": str(exc), "segment_index": index + 1, "segment_status": "error", ...}`.

- [ ] **Step 1: Write failing backend error-code tests**

Create `tests/test_backend_errors.py` with tests that monkeypatch `urllib.request.urlopen` and `sys.modules["ollama"]` to cover:

```python
def test_http_stream_json_decode_error_has_stable_code(self):
    backend = OllamaBackend(OllamaBackendOptions(mode=OllamaMode.HTTP))
    with patch("urllib.request.urlopen", return_value=FakeResponse([b"{bad json}\n"])):
        with self.assertRaises(BackendRequestError) as ctx:
            list(backend.stream_generate("hello"))
    self.assertEqual(ctx.exception.code, "invalid_backend_json")
```

Also cover `TimeoutError` as `"backend_timeout"`, `OSError`/`URLError` as `"ollama_unavailable"`, missing local dependency as `"dependency_missing"`, HTTP 404 as `"model_not_found"`, and missing response content as `"unexpected_backend_response"`.

Run: `python3 -m unittest tests.test_backend_errors -v`

Expected before implementation: failures because errors do not expose these codes.

- [ ] **Step 2: Implement coded backend errors**

Add `code` defaults in `backend/errors.py`. In `backend/ollama_backend.py`, catch `TimeoutError`, `json.JSONDecodeError`, and `OSError` where model calls happen. Preserve existing subclass types when possible and pass explicit `code` values for dependency and invalid JSON cases.

- [ ] **Step 3: Write failing service stream error event test**

In `tests/test_translation_service.py`, patch `OllamaBackend.stream_generate` to raise `BackendRequestError("bad json", code="invalid_backend_json")`, call `list(service.stream_translate(TranslationRequest(text="hello")))`, and assert the last event is an error with `code == "invalid_backend_json"`, `segment_index == 1`, `segment_status == "error"`. Also assert `service.translate(...)` raises `BackendRequestError`.

- [ ] **Step 4: Implement service error events**

Wrap per-segment streaming in `try/except BackendError`. Yield one structured `error` event with active segment fields, then re-raise so `translate()` and API calls still fail instead of returning partial success.

- [ ] **Step 5: Verify**

Run:

```bash
python3 -m unittest tests.test_backend_errors tests.test_translation_service -v
```

## Task 2: API Malformed Payloads and Corrupt Config Recovery

**Files:**
- Modify: `python_backend/api_server.py`
- Modify: `python_backend/config.py`
- Create: `tests/test_api_server.py`
- Create: `tests/test_config_store.py`

**Interfaces:**
- API malformed translate/config requests return status `400` with JSON `{"error": "..."}`.
- `ConfigStore.load()` backs up corrupt content to `<filename>.corrupt`, emits `Translator config corrupt: ...` to stderr, then returns `AppConfig()`.

- [ ] **Step 1: Write failing API tests**

Create `tests/test_api_server.py` using `TranslatorAPIHandler` with a minimal fake handler or `build_server()` on an ephemeral port. Send `/translate` with `{}` and `/config` with an unexpected bad shape such as `{"font_size": "large"}` when that triggers construction failure. Assert response status `400`, content type JSON, and an `error` key.

- [ ] **Step 2: Catch TypeError in API handlers**

Change both handler blocks to `except (TypeError, ValueError) as exc:` and keep existing JSON response behavior.

- [ ] **Step 3: Write failing config corrupt test**

Create `tests/test_config_store.py` with a `TemporaryDirectory`, write invalid JSON to `ui_config.json`, redirect `stderr`, call `ConfigStore(path).load()`, then assert defaults are returned, stderr mentions the path, and `ui_config.json.corrupt` contains the original invalid text.

- [ ] **Step 4: Implement config backup and diagnostic**

In `ConfigStore.load()`, catch JSON/read errors, write the corrupt file to `self.path.with_suffix(self.path.suffix + ".corrupt")`, print a concise diagnostic to `sys.stderr`, and return `AppConfig()`. If backup fails, include that in stderr and still return defaults.

- [ ] **Step 5: Verify**

Run:

```bash
python3 -m unittest tests.test_api_server tests.test_config_store -v
```

## Task 3: Frontend Storage, Polling, and Status Resilience

**Files:**
- Modify: `src/App.tsx`

**Interfaces:**
- `loadHistoryFromStorage(): HistoryItem[]`
- `backupBadStorageValue(key: string, value: string): void`
- `isHistoryItem(value: unknown): value is HistoryItem`
- `inFlightRef` prevents duplicate submissions before React state updates.
- `copyStatusTimeoutRef` and `statusVersionRef` prevent stale delayed status writes.

- [ ] **Step 1: Add guarded storage helpers**

Above `App()`, add helpers that parse `translator_history_v2`, verify an array of objects with string `source`, string `target`, numeric `timestamp`, and string `id`, and move invalid raw content to `translator_history_v2_corrupt_<timestamp>` before returning `[]`.

- [ ] **Step 2: Use guarded history initialization and cleanup refs**

Change `useState<HistoryItem[]>(() => loadHistoryFromStorage())`. Add `inFlightRef`, `copyStatusTimeoutRef`, and `statusVersionRef`. In the unmount cleanup, clear any pending copy-status timeout.

- [ ] **Step 3: Harden `runTranslation()` and `pollProgress()`**

At the start of `runTranslation`, return when `inFlightRef.current` is true, then set it true before calling `setIsSubmitting(true)`. Ensure all non-stream and stream completion/error/failure paths clear `inFlightRef`, `isSubmitting`, and `currentJobIdRef`. Wrap `pollProgress()` in `try/catch/finally`; if `takeTranslationEvents()` rejects and the job is still current, set status to `Error: <message>`.

- [ ] **Step 4: Guard delayed copy status**

Replace inline `setTimeout(() => setStatus(t("done")), 2000)` with a helper that increments `statusVersionRef`, clears any previous timeout, sets copied, and only restores done when the version still matches and no translation is in flight.

- [ ] **Step 5: Verify**

Run:

```bash
/opt/homebrew/bin/npm run build:frontend
```

## Task 4: Progress Container CSS and Full Validation

**Files:**
- Modify: `src/styles.css`

**Interfaces:**
- `.progress-container` is absolute at the top of the output panel, has fixed height, full width, hidden overflow, and does not shift layout.

- [ ] **Step 1: Add CSS**

Add:

```css
.progress-container {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  overflow: hidden;
  background: var(--border-light);
  z-index: 2;
}
```

- [ ] **Step 2: Run complete validation**

Run:

```bash
python3 -m unittest discover -s tests -v
/opt/homebrew/bin/npm run build:frontend
git log --oneline -3
```

Expected: Python tests pass, frontend build passes, and git log shows the worker branch commits.

## Self-Review

- Spec coverage: Bug#3, #6, #8, #9, #10, #12, #16, #17 and improvements #6/#10 are each mapped to a task.
- Placeholder scan: no TBD/TODO/later language remains.
- Type consistency: helper names and error-code strings are defined before use and reused consistently across backend, service, and frontend tasks.
