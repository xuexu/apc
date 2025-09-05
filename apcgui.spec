# apcgui.spec
# -*- mode: python ; coding: utf-8 -*-

import os

REPO_ROOT = os.path.abspath(os.getcwd())
SCRIPT_PATH = os.path.join(REPO_ROOT, "apcgui.py")

datas = [
    (os.path.join(REPO_ROOT, "apc/config"), "config"),
    (os.path.join(REPO_ROOT, "apc/locale"), "locale"),
]


a = Analysis(
    [SCRIPT_PATH],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='apcgui',
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
    name='apcgui',
)
