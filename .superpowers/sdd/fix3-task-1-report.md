# Task 1 Report: Backend Error Codes and Stream Error Events

## Scope

Implemented only the files assigned to Task 1:

- `backend/errors.py`
- `backend/ollama_backend.py`
- `python_backend/services/translation_service.py`
- `tests/test_backend_errors.py`
- `tests/test_translation_service.py`

No frontend files, API/config tests, vault files, or unrelated docs were edited.

## TDD Record

### 1. Backend error-code tests written first

Created `tests/test_backend_errors.py` to cover the required stable codes:

- HTTP stream invalid JSON -> `invalid_backend_json`
- HTTP timeout -> `backend_timeout`
- HTTP `URLError` -> `ollama_unavailable`
- HTTP `OSError` -> `ollama_unavailable`
- Missing local dependency -> `dependency_missing`
- HTTP 404 -> `model_not_found`
- Missing backend response content -> `unexpected_backend_response`

Red run:

```bash
python3 -m unittest tests.test_backend_errors -v
```

Result before implementation: 7 failing/erroring tests, as expected. Failures showed missing `code` attributes and unmapped exceptions.

### 2. Backend implementation

Updated `backend/errors.py` to carry stable `code` values with subclass defaults:

- `BackendError` -> `backend_error`
- `BackendUnavailableError` -> `ollama_unavailable`
- `BackendRequestError` -> `backend_request_failed`
- `ModelNotFoundError` -> `model_not_found`

Updated `backend/ollama_backend.py` to:

- preserve existing `BackendError` subclasses when already raised
- map local import failure to `dependency_missing`
- map malformed JSON to `invalid_backend_json`
- map timeouts to `backend_timeout`
- map `OSError`/`URLError` reachability failures to `ollama_unavailable`
- map missing content in backend payloads to `unexpected_backend_response`

Green run after implementation:

```bash
python3 -m unittest tests.test_backend_errors -v
```

Result: all backend error-code tests passed.

### 3. Service error-event test written before service implementation

Extended `tests/test_translation_service.py` with a segment-stream failure test that:

- forces `OllamaBackend.stream_generate` to raise `BackendRequestError("bad json", code="invalid_backend_json")`
- verifies the stream emits a structured `error` event for segment 1
- verifies the same backend error is re-raised
- verifies `translate(...)` still raises `BackendRequestError`

Because the implementation requirement is to yield the error event and then re-raise, the test captures events by iterating the generator manually instead of using `list(...)`; `list(...)` would discard emitted items once the generator re-raises.

Red run:

```bash
python3 -m unittest tests.test_translation_service -v
```

Result before implementation: the new test failed because the stream emitted only `started` and then raised immediately.

### 4. Service implementation

Updated `python_backend/services/translation_service.py` to wrap each translatable segment's streaming work in `try/except BackendError` and:

- emit a structured `error` event including:
  - `event: "error"`
  - `code`
  - `message`
  - `segment_index`
  - `segment_status: "error"`
  - active segment metadata
  - current rendered output and completed segment count
- re-raise the original backend exception so `translate()` and API consumers still fail rather than returning partial success

Green run after implementation:

```bash
python3 -m unittest tests.test_translation_service -v
```

Result: all translation service tests passed.

## Final Verification

Executed the task-level verification command from the brief:

```bash
python3 -m unittest tests.test_backend_errors tests.test_translation_service -v
```

Result: 15 tests passed.

## Files Changed

- `backend/errors.py`
- `backend/ollama_backend.py`
- `python_backend/services/translation_service.py`
- `tests/test_backend_errors.py`
- `tests/test_translation_service.py`

## Concerns

- The brief's sample for the service test says to call `list(service.stream_translate(...))` and also require re-raise semantics. Those two requirements conflict, because a generator that re-raises after yielding an `error` event cannot be fully materialized with `list(...)`. The implemented behavior follows the plan's stated runtime requirement: emit `error`, then re-raise. The test was written to match that actual contract.
