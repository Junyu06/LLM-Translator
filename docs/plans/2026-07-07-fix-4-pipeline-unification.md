# Pipeline Unification and Audit Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify the core and desktop streaming translation pipeline, validate request fields at construction, remove broad NSIS process-kill behavior, and close out the audit campaign documentation.

**Architecture:** Move the streaming prompt/postprocess loop into `core.pipeline` so both core and desktop paths share the same segmentation and extraction behavior. Keep `TranslationService` as a request adapter: normalize input, build `PipelineOptions`, validate budgets, create backend, and convert core pipeline updates into bridge/API event dictionaries. Dataclass models own user-readable field validation so bridge/API callers fail consistently before service execution.

**Tech Stack:** Python 3.14 `unittest`; React/Vite build for frontend validation; Tauri 2 / Rust `cargo check`; NSIS hook static edit only, not Windows-tested in this worker run.

## Global Constraints

- Behavior must not change: existing translation service tests must pass before and after the refactor.
- `core/pipeline.py` owns shared segmentation, prompt construction, streaming chunk accumulation, and postprocess.
- `python_backend/services/translation_service.py` only adapts requests/backend/results to event dictionaries and response dataclasses.
- Request field validation must reject invalid `mode`, language, output mode, translation mode, layout/theme/ui language, booleans, and integer budget/font fields with user-readable `ValueError`s.
- NSIS hook must not kill by broad process name and must not use fixed `Sleep 500`; use a bounded wait loop and document that this was statically changed, not Windows-tested.
- Update repo docs only for facts made current by this campaign.

---

## Task 1: Shared Streaming Pipeline

**Files:**
- Modify: `core/pipeline.py`
- Modify: `core/__init__.py`
- Modify: `python_backend/services/translation_service.py`
- Modify: `tests/test_translation_service.py`

**Steps:**
- [ ] Add `SplitMode.MARKDOWN`, `PipelineStreamUpdate`, and `iter_streaming_pipeline()` in `core/pipeline.py`.
- [ ] Make `make_segments()` handle Markdown block splitting through `split_markdown_blocks()`.
- [ ] Write/keep snapshot tests proving Markdown protected blocks, passthrough segments, partial streaming updates, completion, and error event behavior remain unchanged.
- [ ] Replace service-local prompt/postprocess loop with `iter_streaming_pipeline()` and event adaptation.
- [ ] Run `python3 -m unittest tests.test_translation_service -v`.

## Task 2: Request Field Validation

**Files:**
- Modify: `python_backend/models.py`
- Create: `tests/test_models_validation.py`

**Steps:**
- [ ] Add dataclass `__post_init__` validation for `AppConfig` and `TranslationRequest`.
- [ ] Reject invalid enum-like fields and wrong primitive types with concise `ValueError` messages naming the field.
- [ ] Reject target language `auto`, but allow source language `auto`.
- [ ] Add focused tests for invalid `mode`, `source_lang`, `target_lang`, `output_mode`, `translation_mode`, booleans, and integer budget/font fields.
- [ ] Run `python3 -m unittest tests.test_models_validation tests.test_api_server -v`.

## Task 3: NSIS Hook and Documentation Closeout

**Files:**
- Modify: `src-tauri/windows/installer-hooks.nsh`
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `README.zh.md`
- Modify: `docs/audits/2026-07-07-health-audit.md`

**Steps:**
- [ ] Replace process-name kill macro with a bounded wait loop that checks for sidecar exit and does not call `KillProcess*`.
- [ ] Remove fixed `Sleep 500`; bounded waits should use small poll sleeps and a maximum attempt count.
- [ ] Update AGENTS/README validation notes with current test/build commands and startup logging/config recovery facts.
- [ ] Add audit fix status line pointing to the four fix commits and note NSIS change is static/not Windows-tested.
- [ ] Run `python3 -m unittest discover -s tests -v`, `python3 core_test.py && python3 test_core_smoke.py`, `/opt/homebrew/bin/npm run build:frontend`, `~/.cargo/bin/cargo check --manifest-path src-tauri/Cargo.toml`, and `git log --oneline -5`.

## Self-Review

- Spec coverage: Bug#14/#15/#18 and improvement #9 map to Tasks 1-3.
- Placeholder scan: no TBD/TODO/later placeholders.
- Type consistency: new core pipeline update type is exported and consumed only through service adapter.
