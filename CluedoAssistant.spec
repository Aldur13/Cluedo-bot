# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# scikit-learn and matplotlib both lazily import compiled submodules that
# PyInstaller's static analysis can't discover on its own -- pull in every
# submodule explicitly rather than debugging missing-module crashes one at a
# time after packaging.
hidden_imports = (
    collect_submodules("sklearn")
    + collect_submodules("matplotlib.backends")
)
extra_datas = collect_data_files("matplotlib") + collect_data_files("sklearn")

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('cluedo/data', 'cluedo/data')] + extra_datas,
    hiddenimports=hidden_imports,
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
    a.datas,
    [],
    name='CluedoAssistant',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
