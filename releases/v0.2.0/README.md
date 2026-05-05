# Translator v0.2.0

Release artifacts for Translator 0.2.0.

## Artifacts

- `Translator_0.2.0_aarch64.dmg` - macOS Apple Silicon installer image.
- `Translator_0.2.0_x64-setup.exe` - Windows x64 NSIS installer.

## Build Notes

- Source commit: `a876444190df6734afb1a3361cbaf62350617069`
- macOS DMG built locally on 2026-05-05 from `main`.
- macOS app bundle is ad-hoc signed, not notarized.
- Windows installer was produced from the Windows packaging path added in `v0.2.0`.

## Verification

- `npm run tauri:build` compiled the macOS release app; the default DMG step failed, so the DMG was rebuilt from the generated app with Tauri's generated `bundle_dmg.sh`.
- `hdiutil verify releases/v0.2.0/Translator_0.2.0_aarch64.dmg` passed.
- `file releases/v0.2.0/Translator_0.2.0_x64-setup.exe` identifies the Windows package as a GUI NSIS installer.

