# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — OptiLag (Windows)
# Build: pyinstaller OptiLag.spec

import sys
from pathlib import Path

block_cipher = None
root = Path(SPECPATH)

datas = []
icons = root / "icons"
if icons.is_dir():
    datas.append((str(icons), "icons"))
conf = root / "conf"
if conf.is_dir():
    datas.append((str(conf), "conf"))

hidden = [
    "customtkinter",
    "PIL",
    "PIL._tkinter_finder",
    "optilag_backend",
    "optilag_backend.network",
    "optilag_backend.routing",
    "optilag_backend.core",
    "optilag_backend.tunnel",
    "optilag_backend.bridge",
]

a = Analysis(
    ["optilag_pubg.py"],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# collect customtkinter package data
try:
    from PyInstaller.utils.hooks import collect_all
    ctk_datas, ctk_binaries, ctk_hidden = collect_all("customtkinter")
    a.datas += ctk_datas
    a.binaries += ctk_binaries
    a.hiddenimports += ctk_hidden
except Exception:
    pass

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="OptiLag",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # sem consola preta
    disable_windowed_traceback=False,
    argv_emulation=False,
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
    upx=True,
    upx_exclude=[],
    name="OptiLag",
)
