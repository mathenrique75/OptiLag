# -*- mode: python ; coding: utf-8 -*-
# OptiLag — PyInstaller (Windows)
# Build: python -m PyInstaller OptiLag.spec --noconfirm

from PyInstaller.utils.hooks import collect_all

block_cipher = None

datas = []
binaries = []
hiddenimports = [
    "customtkinter",
    "PIL",
    "PIL._tkinter_finder",
    "pyotp",
    "optilag_backend",
    "optilag_backend.network",
    "optilag_backend.network.probes",
    "optilag_backend.routing",
    "optilag_backend.routing.graph",
    "optilag_backend.routing.simulator",
    "optilag_backend.core",
    "optilag_backend.core.engine",
    "optilag_backend.tunnel",
    "optilag_backend.tunnel.wireguard",
    "optilag_backend.bridge",
    "optilag_backend.models",
    "optilag_backend.persistence",
]

# customtkinter assets
try:
    ctk_datas, ctk_binaries, ctk_hidden = collect_all("customtkinter")
    datas += ctk_datas
    binaries += ctk_binaries
    hiddenimports += ctk_hidden
except Exception:
    pass

# Optional folders (only if they exist — avoids bad TOC entries)
import os
from pathlib import Path

root = Path(SPECPATH)
for folder, dest in (("icons", "icons"), ("conf", "conf")):
    p = root / folder
    if p.is_dir():
        datas.append((str(p), dest))

a = Analysis(
    ["optilag_pubg.py"],
    pathex=[str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

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
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="OptiLag",
)
