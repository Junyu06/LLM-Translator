# Translator Health Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or delegated explorer agents to execute this audit task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce `docs/audits/2026-07-07-health-audit.md`, a Chinese health audit and Windows startup-latency diagnosis for Translator.

**Architecture:** This is a diagnosis-only branch. Inspect each runtime slice independently, run available local validation, collect file-and-line evidence, and aggregate findings into one audit document without behavior changes. Trivial typo/dead-code fixes are allowed only if they do not alter runtime behavior; otherwise record the issue for a later repair task.

**Tech Stack:** React/Vite/TypeScript frontend, Tauri/Rust desktop shell, Python service and bridge, Ollama backend integration, PyInstaller/NSIS Windows packaging.

## Global Constraints

- Do not make behavior changes in this audit item.
- Write the final audit report in Chinese.
- The report must include these five sections: 启动慢诊断, Bug 清单, 改进机会 Top 10, 已顺手修复项, 环境限制与未验证项.
- Every bug entry must include `file:line` evidence or a reproducible command/result.
- Windows is not available in this worker run; record Windows-specific conclusions as static-analysis findings and give a five-minute user-side Windows validation checklist.
- Local environment expectation from queue: `python3` is available; `/opt/homebrew/bin/node` and `/opt/homebrew/bin/npm` are available; `cargo` may be unavailable and must be recorded if skipped.
- Follow `AGENTS.md`: keep Windows bridge bundled via `src-tauri/tauri.windows-bridge.conf.json`, do not switch back to PyInstaller one-file mode, and keep TSX/UI-only actions away from Python bridge calls.

---

## File Map

- Create: `docs/audits/2026-07-07-health-audit.md` - final Chinese audit report.
- Create: `docs/plans/2026-07-07-health-audit.md` - this implementation plan.
- Inspect: `core/*.py` - translation segmentation, prompt, pipeline, post-processing.
- Inspect: `backend/*.py` - Ollama request and error behavior.
- Inspect: `python_backend/*.py` and `python_backend/services/*.py` - API server, bridge protocol, config loading, translation service.
- Inspect: `src-tauri/src/*.rs`, `src-tauri/tauri*.conf.json`, `src-tauri/windows/installer-hooks.nsh` - app startup, Python bridge spawning, window/hotkey lifecycle, Windows packaging config.
- Inspect: `src/App.tsx`, `src/*.ts`, `src/styles.css` - frontend startup, bridge call boundaries, state and UI risks.
- Inspect: `*.spec`, `scripts/*.mjs`, `releases/` if present - Python/Windows packaging and release artifact paths.

---

### Task 1: Baseline Inventory And Local Validation

**Files:**
- Read: `AGENTS.md`
- Read: `README.md`
- Read: `package.json`
- Read: Python test files under `tests/` and repository root
- Record in: `docs/audits/2026-07-07-health-audit.md`

**Interfaces:**
- Produces: a command/result table for the final report.
- Produces: environment constraints for startup-latency conclusions.

- [ ] **Step 1: Capture tool availability**

Run:

```bash
python3 --version
/opt/homebrew/bin/node --version
/opt/homebrew/bin/npm --version
cargo --version
```

Expected: record exact versions. If `cargo` is missing, mark Tauri build as skipped.

- [ ] **Step 2: Run Python tests**

Run:

```bash
python3 -m unittest discover -s tests -v
python3 core_test.py
python3 test_core_pipeline.py
python3 test_core_smoke.py
python3 test_context_verify.py
python3 test_pipepline_local.py
```

Expected: record PASS/FAIL/SKIP and any failure output. Test failures are audit findings, not automatic task failure.

- [ ] **Step 3: Run frontend build if dependencies are present**

Run:

```bash
/opt/homebrew/bin/npm run build:frontend
```

Expected: record PASS/FAIL. If dependencies are missing, run `/opt/homebrew/bin/npm install` only if needed and record it.

- [ ] **Step 4: Run Tauri preflight without building**

Run:

```bash
/opt/homebrew/bin/npm run tauri:preflight
```

Expected: record PASS/FAIL and whether the preflight reports missing Rust/Cargo.

---

### Task 2: Core And Backend Audit

**Files:**
- Inspect: `core/pipeline.py`
- Inspect: `core/splitter.py`
- Inspect: `core/prompt.py`
- Inspect: `core/postprocess.py`
- Inspect: `core/lang.py`
- Inspect: `backend/ollama_backend.py`
- Inspect: `backend/errors.py`
- Record in: `docs/audits/2026-07-07-health-audit.md`

**Interfaces:**
- Produces: translation-pipeline bugs and improvement opportunities.
- Produces: backend error-handling findings for the Top 10 list.

- [ ] **Step 1: Trace translation flow**

Identify entrypoints used by `python_backend/services/translation_service.py` and list the exact calls into `core/` and `backend/`.

- [ ] **Step 2: Check segmentation and context behavior**

Look for empty-input handling, oversized segment behavior, ordering bugs, mutable shared state, and post-processing that can corrupt Markdown or code blocks.

- [ ] **Step 3: Check Ollama failure modes**

Look for timeouts, missing model handling, HTTP error preservation, JSON parsing, and user-facing error clarity.

- [ ] **Step 4: Record evidence**

For each finding, include `file:line`, the bad path, severity, and whether it affects startup, translation correctness, or user feedback.

---

### Task 3: Python Service And Bridge Startup Audit

**Files:**
- Inspect: `python_backend/api_server.py`
- Inspect: `python_backend/bridge.py`
- Inspect: `python_backend/config.py`
- Inspect: `python_backend/models.py`
- Inspect: `python_backend/services/translation_service.py`
- Inspect: `tests/test_bridge_output.py`
- Inspect: `tests/test_translation_service.py`
- Record in: `docs/audits/2026-07-07-health-audit.md`

**Interfaces:**
- Produces: bridge spawn and backend initialization risks.
- Produces: macOS reproducible profiling commands for the startup section.

- [ ] **Step 1: Trace bridge command startup**

Find the bridge command parser and identify whether `health`, `config`, `translate`, or OCR/model actions import or initialize heavy modules before they are needed.

- [ ] **Step 2: Measure local bridge latency**

Run:

```bash
time python3 python_backend/bridge.py health
time python3 python_backend/bridge.py config
```

Expected: record rough wall-clock times and output shape.

- [ ] **Step 3: Check JSON/stdout protocol**

Verify successful and error responses are ASCII-safe JSON on stdout and do not mix logging or warnings into the protocol stream.

- [ ] **Step 4: Record evidence**

For each finding, include `file:line`, startup segment, severity, and whether Windows packaging may amplify the cost.

---

### Task 4: Tauri Shell And Frontend Audit

**Files:**
- Inspect: `src-tauri/src/main.rs`
- Inspect: `src-tauri/src/hotkey_macos.rs`
- Inspect: `src-tauri/src/hotkey_windows.rs`
- Inspect: `src-tauri/tauri.conf.json`
- Inspect: `src/App.tsx`
- Inspect: `src/main.tsx`
- Inspect: `src/types.ts`
- Record in: `docs/audits/2026-07-07-health-audit.md`

**Interfaces:**
- Produces: Tauri shell startup, spawn, global hotkey, and UI bridge-boundary findings.
- Produces: frontend loading and user-interaction improvement opportunities.

- [ ] **Step 1: Segment desktop startup**

Map the startup path as Tauri process start -> setup hooks -> window creation -> Python bridge calls -> frontend mount -> first backend health/config/translate calls.

- [ ] **Step 2: Check Python bridge boundaries**

Confirm settings, layout, theme, and local UI actions do not call Python. Flag any UI-only action that invokes the bridge.

- [ ] **Step 3: Check child-process behavior**

Inspect Windows process spawning for hidden console behavior, repeated bridge spawn patterns, and synchronous waits on UI-triggered paths.

- [ ] **Step 4: Check frontend risks**

Look for stale closures, unbounded local storage/config writes, event listener leaks, large initial render work, and fragile error handling.

- [ ] **Step 5: Record evidence**

For each finding, include `file:line`, affected startup segment, severity, and whether it is macOS-only, Windows-only, or cross-platform.

---

### Task 5: Windows Packaging And Startup-Latency Diagnosis

**Files:**
- Inspect: `Translator.spec`
- Inspect: `Translator_windows.spec`
- Inspect: `Translator_bridge_windows.spec`
- Inspect: `scripts/build-python-bridge.mjs`
- Inspect: `scripts/check-tauri-env.mjs`
- Inspect: `src-tauri/tauri.windows-bridge.conf.json`
- Inspect: `src-tauri/windows/installer-hooks.nsh`
- Inspect: `package.json`
- Record in: `docs/audits/2026-07-07-health-audit.md`

**Interfaces:**
- Produces: Windows-specific startup latency hypotheses.
- Produces: five-minute Windows validation checklist.

- [ ] **Step 1: Verify bridge packaging mode**

Confirm whether the release path builds the Python bridge as one-dir or one-file and whether Tauri bundles the directory through `src-tauri/tauri.windows-bridge.conf.json`.

- [ ] **Step 2: Identify Windows latency amplifiers**

Assess PyInstaller extraction, antivirus scanning, WebView2 initialization, NSIS install path, bridge spawn frequency, PATH/environment lookup, and console window suppression.

- [ ] **Step 3: Draft user-side Windows validation checklist**

Include commands or actions that can be completed in five minutes: launch timing, bridge `health` timing, second-launch timing, antivirus exclusion comparison if available, and WebView2 runtime check.

- [ ] **Step 4: Record evidence**

For each hypothesis, include confidence, evidence, what would confirm it on Windows, and expected fix direction.

---

### Task 6: Assemble Audit Report And Validate

**Files:**
- Create: `docs/audits/2026-07-07-health-audit.md`

**Interfaces:**
- Consumes: findings from Tasks 1-5.
- Produces: final Chinese report satisfying the queue validation.

- [ ] **Step 1: Create the report with required sections**

Use this exact top-level section set:

```markdown
# Translator 健康审计与 Windows 启动慢诊断

## 摘要
## 启动慢诊断
## Bug 清单
## 改进机会 Top 10
## 已顺手修复项
## 环境限制与未验证项
## 验证记录
```

- [ ] **Step 2: Rank findings**

Rank bug severity as Critical, High, Medium, Low. Rank improvement opportunities by impact/cost and keep exactly 10 entries.

- [ ] **Step 3: Validate required text**

Run:

```bash
test -f docs/audits/2026-07-07-health-audit.md
grep -c "启动慢诊断\\|Bug 清单\\|改进机会\\|顺手修复\\|环境限制" docs/audits/2026-07-07-health-audit.md
```

Expected: second command prints `5` or higher.

- [ ] **Step 4: Commit branch output**

Run:

```bash
git add docs/plans/2026-07-07-health-audit.md docs/audits/2026-07-07-health-audit.md
git commit -m "docs: add Translator health audit"
git log --oneline -3
```

Expected: latest commits include this audit work.
