# Translator Dev Rules

## Build And Packaging

- Use `npm run build:windows` or `npm run tauri:build:windows` for Windows release packages.
- Keep `npm run tauri:build` platform-neutral. Do not add Windows-only Python bridge resources to `src-tauri/tauri.conf.json`.
- Windows packaging must use `src-tauri/tauri.windows-bridge.conf.json` to bundle `src-tauri/binaries/translator-bridge/` as `translator-bridge/`.
- Build the Windows Python bridge through `scripts/build-python-bridge.mjs`; do not hand-copy bridge files into the bundle.
- Do not switch the bridge back to PyInstaller one-file mode for normal release builds. One-file extraction adds user-visible startup latency when commands spawn the bridge repeatedly.

## Runtime Boundaries

- TSX/UI-only actions must not call Python. Settings tabs, theme/language changes, layout toggles, and other local config flows should stay in React/Tauri/Rust local JSON.
- Python bridge calls are reserved for real backend work: translation, OCR/model operations, and explicit backend health checks.
- `get_config`, `save_config`, tray/minimize flags, and hotkey enablement must stay Rust-side unless there is a concrete backend dependency.
- If a UI click feels like compilation or blocks for bridge startup, treat it as a boundary bug, not as acceptable desktop behavior.

## Windows Child Processes

- Windows child processes launched from Tauri must not show console windows for normal app interactions.
- Keep the PyInstaller bridge console subsystem enabled so stdout/stderr pipes work, but launch it from Rust with `CREATE_NO_WINDOW`.
- Apply the same hidden-child-process rule to clipboard helpers and other PowerShell/cmd child processes.
- Keep Python bridge stdout/stderr protocol ASCII-safe JSON. Use escaped JSON output rather than raw non-ASCII text because packaged Windows processes can inherit legacy code pages and fail with `charmap` encode errors.

## Validation

- Before calling a Windows package ready, run `npm run tauri:build:windows`.
- Verify the bridge executable responds to `src-tauri/binaries/translator-bridge/translator-bridge.exe health`.
- Verify generated installer manifests include `translator-bridge` directory entries.
- Run backend unit tests with `venv\Scripts\python.exe -m unittest discover -s tests -v`.
