# -*- mode: python ; coding: utf-8 -*-

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
        "python_backend",
        "python_backend.config",
        "python_backend.models",
        "python_backend.services.translation_service",
        "ui_windows.hotkey_windows",
        "ui_windows.ocr",
        "winsdk",
        "winsdk.windows.media.ocr",
        "winsdk.windows.graphics.imaging",
        "winsdk.windows.storage.streams",
        "PIL",
        "PIL.Image",
        "PIL.ImageGrab",
        "PIL.ImageDraw",
        "pystray",
        "keyboard",
        "pyperclip",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    upx=True,
    # Keep the console subsystem so stdout/stderr pipes work.
    # The Tauri shell starts this process with CREATE_NO_WINDOW on Windows.
    console=True,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="translator-bridge",
)
