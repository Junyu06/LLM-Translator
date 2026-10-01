# -*- mode: python ; coding: utf-8 -*-
# The Python bridge as a folder the macOS app carries in its Resources, so the
# installed app does not depend on a source checkout or its virtualenv.

import os

project_root = os.path.abspath(os.getcwd())

a = Analysis(
    ["python_backend/bridge.py"],
    pathex=[project_root],
    binaries=[],
    datas=[],
    hiddenimports=[
        "backend",
        "core",
        "markdown_it",
        "python_backend",
        "python_backend.clipboard",
        "python_backend.config",
        "python_backend.models",
        "python_backend.services.translation_service",
        "ui_mac.ocr",
        "AppKit",
        "Foundation",
        "Quartz",
        "Vision",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Windows-only modules the bridge imports lazily.
    excludes=["ui_windows", "pyperclip", "tkinter"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="translator-bridge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="translator-bridge",
)
