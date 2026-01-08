# -*- mode: python ; coding: utf-8 -*-


import os
from PyInstaller.utils.hooks import collect_submodules

spec_dir = os.path.dirname(globals().get("__file__", os.getcwd()))
project_root = os.path.abspath(spec_dir)

a = Analysis(
    ['ui_mac/app.py'],
    pathex=[project_root],
    binaries=[],
    datas=[
        ('ui_mac/hotkey_helper.py', 'ui_mac'),
        ('ui_mac/menu_helper.py', 'ui_mac'),
        ('backend', 'backend'),
        ('core', 'core'),
        ('ui_mac', 'ui_mac'),
    ],
    hiddenimports=[
        "__future__",
        "AppKit",
        "Foundation",
        "Quartz",
        "Vision",
        "objc",
        "ui_mac.hotkey_helper",
        "ui_mac.menu_helper",
        "PyObjCTools",
        "PyObjCTools.AppHelper",
    ] + collect_submodules("backend") + collect_submodules("core") + collect_submodules("ui_mac") + collect_submodules("PyObjCTools"),
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
    name='Translator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Translator',
)
app = BUNDLE(
    coll,
    name='Translator.app',
    icon=None,
    bundle_identifier=None,
)
