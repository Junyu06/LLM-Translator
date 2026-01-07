# -*- mode: python ; coding: utf-8 -*-

import os

project_root = os.path.abspath(os.getcwd())

a = Analysis(
    ['ui_windows/app.py'],
    pathex=[project_root],
    binaries=[],
    datas=[],
    hiddenimports=[
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
    a.binaries,
    a.zipfiles,
    a.datas,
    name='Translator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)
