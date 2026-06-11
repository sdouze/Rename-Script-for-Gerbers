# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

# tkinterdnd2 ships a native tkdnd library, and customtkinter ships theme
# assets (JSON/fonts) -- both must be bundled or the packaged .exe will fail.
dnd_datas, dnd_binaries, dnd_hidden = collect_all('tkinterdnd2')
ctk_datas, ctk_binaries, ctk_hidden = collect_all('customtkinter')

a = Analysis(
    ['gui_dragdrop.py'],
    pathex=[],
    binaries=dnd_binaries + ctk_binaries,
    datas=dnd_datas + ctk_datas,
    hiddenimports=dnd_hidden + ctk_hidden,
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
    name='gui_dragdrop',
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
