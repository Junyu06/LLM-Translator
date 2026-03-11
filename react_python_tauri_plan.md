# React + Python + Tauri Migration Plan

## Goal

Migrate the current Tk desktop UI to a single cross-platform desktop client built with:

- React for the application UI
- Tauri for the desktop shell and packaging
- Python for translation, OCR, and existing business logic

The target outcome is:

- one shared UI for macOS and Windows
- less duplicated platform-specific UI code
- higher UI ceiling than `tkinter/ttk`
- reuse of the current Python translation pipeline instead of rewriting core logic

## Current State

The project is split like this:

- `core/`: prompt building, splitting, output rendering, post-processing
- `backend/`: Ollama backend integration
- `ui_mac/`: macOS Tk UI, hotkey, OCR integration
- `ui_windows/`: Windows Tk UI, hotkey, OCR integration

Current pain points:

- the UI is duplicated across `ui_mac/` and `ui_windows/`
- visual refinement is limited by Tk
- modern component patterns must be built manually
- desktop-specific logic and UI logic are mixed together

## Target Architecture

Suggested high-level structure:

```text
translator-app/
  src/                     # React UI
  src-tauri/               # Tauri shell, commands, packaging
  python_backend/
    api_server.py          # local API entrypoint
    services/              # translation / OCR / config services
    core/                  # migrated from current core/
    backend/               # migrated from current backend/
  scripts/
  tests/
```

Runtime model:

1. Tauri launches the desktop app.
2. Tauri starts the embedded Python backend as a child process.
3. React talks to the Python backend over local IPC or localhost HTTP.
4. Tauri handles native desktop features.

Responsibility split:

- React:
  - input/output UI
  - settings screen
  - status display
  - history or glossary UI later
- Tauri:
  - app window
  - tray
  - global shortcut registration
  - clipboard/image access if needed
  - packaging and installers
- Python:
  - translation pipeline
  - Ollama calls
  - OCR orchestration
  - language/config/business rules

## What To Keep

Keep and reuse with minimal rewrite:

- `core/prompt.py`
- `core/pipeline.py`
- `core/postprocess.py`
- `core/splitter.py`
- `core/lang.py`
- `backend/ollama_backend.py`
- most test logic around translation behavior

These files already represent the real product logic. They should move behind a stable Python service boundary instead of being called directly from Tk.

## What To Replace

Replace or retire:

- `ui_mac/app.py`
- `ui_windows/app.py`
- most Tk-specific state and widget code
- duplicated platform UI layout logic

Refactor platform-specific helpers:

- `ui_mac/hotkey_mac.py`
- `ui_windows/hotkey_windows.py`
- `ui_mac/ocr.py`
- `ui_windows/ocr.py`

Some of that logic may move:

- into Tauri native capabilities
- into Python services
- or remain platform-specific modules called by the Python backend

## Recommended Communication Model

Preferred first version:

- Python backend exposes a small local HTTP API on `127.0.0.1`
- React calls it with normal fetch requests
- Tauri starts/stops the Python process

Why this is the best first step:

- simplest to debug
- React side stays standard
- Python side is easy to test separately
- avoids over-coupling the UI to Tauri command APIs

Suggested API surface:

- `POST /translate`
- `POST /ocr`
- `GET /config`
- `PUT /config`
- `GET /health`

Possible `POST /translate` request fields:

- `text`
- `source_lang`
- `target_lang`
- `use_context`
- `collapse_newlines`
- `output_mode`
- `layout`
- `model`
- `mode`
- `host`

## UI Scope For React

Phase 1 UI should stay narrow and tool-like:

- main translation screen
- source/target language selectors
- model/backend controls
- output mode and layout controls
- translate / stop actions
- settings panel
- status and error area

Do not overbuild in the first migration:

- no account system
- no cloud sync
- no heavy design system work
- no large plugin architecture

The first objective is not "make it flashy". It is "make it cleaner, shared, and easier to evolve".

## Native Desktop Features

Features currently handled per-platform in Tk should move into Tauri where possible:

- global shortcut
- tray
- window show/hide
- clipboard read
- app lifecycle
- packaging

Features that may still stay in Python:

- OCR invocation
- translation orchestration
- config persistence format

Need validation during implementation:

- whether image clipboard extraction is easier through Tauri plugins or existing Python platform code
- whether global double-copy behavior should be implemented in Tauri or preserved in Python helpers

## Migration Phases

### Phase 0: Stabilize Boundaries

- freeze Tk UI feature work except bug fixes
- identify business logic that must remain Python
- define a backend API contract
- keep existing tests passing

Deliverable:

- a clear Python service interface independent from Tk widgets

### Phase 1: Extract Python Service

- create `python_backend/`
- wrap current translation flow in API endpoints
- add config load/save service
- add health check endpoint
- add tests around endpoint behavior

Deliverable:

- Python backend runnable without Tk

### Phase 2: Create Tauri + React Shell

- scaffold Tauri app
- build the main translation screen in React
- wire React to local backend API
- launch Python backend from Tauri on app startup

Deliverable:

- a working desktop app that can translate text end-to-end

### Phase 3: Rebuild Native Features

- tray support
- global shortcut support
- clipboard flow
- image paste / OCR flow
- settings persistence integration

Deliverable:

- parity with current daily-use behavior

### Phase 4: Packaging

- macOS packaging and signing workflow
- Windows packaging workflow
- ship Python runtime with the desktop app
- verify backend path resolution in packaged mode

Deliverable:

- installable builds for macOS and Windows

### Phase 5: Cleanup

- remove Tk-specific UI code once parity is confirmed
- keep only fallback scripts if needed
- update docs and developer setup

Deliverable:

- single maintained desktop UI stack

## Risks

### Packaging Complexity

Biggest technical risk is not React itself. It is bundling Python cleanly inside a Tauri app on both macOS and Windows.

Mitigation:

- prove packaging early with a minimal backend
- do not wait until the full UI is done

### Native Feature Parity

Clipboard image handling, OCR, and double-copy hotkey behavior may be more awkward than the basic translation flow.

Mitigation:

- treat these as explicit parity milestones
- do not assume they come for free from Tauri

### Process Management

The app will move from a simple single-process Tk model to a multi-process desktop model.

Mitigation:

- define startup, shutdown, retry, and health-check behavior early
- add backend crash handling in the Tauri shell

### Scope Creep

Once React is introduced, it becomes easy to overdesign the UI.

Mitigation:

- keep phase 1 and phase 2 focused on parity and structure
- improve visuals only after the architecture is stable

## Recommended Stack

Frontend:

- React
- TypeScript
- Vite
- a lightweight component approach, not a heavy design system on day one

Desktop shell:

- Tauri v2

Python backend:

- FastAPI or Flask
- existing `core/` and `backend/` modules migrated into a service package

Testing:

- keep current Python tests
- add API tests
- add a few UI integration tests later if needed

## Practical Recommendation

This migration is worth doing if the app is expected to keep growing beyond a simple utility window.

It is probably worth it if future plans include:

- settings pages that keep expanding
- history
- glossary or terminology controls
- richer OCR flows
- better status/error UX
- cleaner cross-platform maintenance

It is probably not worth it if the app will remain:

- a very small personal tool
- feature-stable
- mostly text in, text out

## Immediate Next Steps

1. Extract the current translation workflow behind a backend function that does not depend on Tk state.
2. Define the first API contract for `/translate`, `/config`, and `/health`.
3. Create a minimal Tauri + React shell that can call a dummy Python backend.
4. Validate packaged startup on both macOS and Windows before rebuilding the whole UI.

## Definition Of Success

The migration is successful when:

- one React UI replaces both `ui_mac/app.py` and `ui_windows/app.py`
- Python remains the source of truth for translation logic
- the packaged app runs on macOS and Windows
- global shortcut, clipboard flow, OCR, and settings all work at parity
- future UI changes no longer require maintaining two separate desktop frontends
