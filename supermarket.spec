# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Supermarket App
Run:  pyinstaller supermarket.spec
"""

import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_all

# ── Collect all Streamlit assets (HTML, CSS, JS, etc.) ──────────────────────
streamlit_datas, streamlit_binaries, streamlit_hiddenimports = collect_all("streamlit")

# ── Collect sklearn data files ───────────────────────────────────────────────
sklearn_datas, sklearn_binaries, sklearn_hiddenimports = collect_all("sklearn")

# ── Altair / vega (Streamlit depends on it for charts) ──────────────────────
altair_datas, altair_binaries, altair_hiddenimports = collect_all("altair")

# ── Additional data files ─────────────────────────────────────────────────────
extra_datas = [
    ("app.py", "."),           # The actual Streamlit app
]

all_datas    = streamlit_datas    + sklearn_datas    + altair_datas    + extra_datas
all_binaries = streamlit_binaries + sklearn_binaries + altair_binaries
all_hidden   = streamlit_hiddenimports + sklearn_hiddenimports + altair_hiddenimports + [
    # numpy / pandas hidden imports
    "numpy",
    "numpy.core._methods",
    "numpy.lib.format",
    "pandas",
    "pandas._libs.tslibs.timedeltas",
    "pandas._libs.tslibs.np_datetime",
    "pandas._libs.tslibs.nattype",
    "pandas._libs.skiplist",
    # sklearn
    "sklearn.utils._cython_blas",
    "sklearn.neighbors.typedefs",
    "sklearn.neighbors._partition_nodes",
    "sklearn.tree._utils",
    "sklearn.ensemble._forest",
    # stdlib
    "sqlite3",
    "hashlib",
    "email.mime.multipart",
    "email.mime.text",
]

block_cipher = None

a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=all_binaries,
    datas=all_datas,
    hiddenimports=all_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib.tests", "numpy.random._examples"],
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
    exclude_binaries=True,   # Use COLLECT for a folder-based dist (faster startup)
    name="SupermarketApp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,            # Keep console so user sees the server URL + network IP
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SupermarketApp",   # Output folder: dist/SupermarketApp/
)
