# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_submodules


def _existing(path):
    return os.path.exists(path)


datas = [
    ('help_en.html', '.'),
    ('help_es.html', '.'),
]

if _existing('Figtree-VariableFont_wght.ttf'):
    datas.append(('Figtree-VariableFont_wght.ttf', '.'))

if _existing('assets'):
    datas.append(('assets', 'assets'))

if _existing('icon.png'):
    datas.append(('icon.png', '.'))
if _existing('doer_logo.png'):
    datas.append(('doer_logo.png', '.'))


a = Analysis(
    ['CanvasAssignments.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=collect_submodules('keyring'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

icon_path = None
if sys.platform == 'darwin' and _existing('icon.icns'):
    icon_path = 'icon.icns'

entitlements_path = None
if sys.platform == 'darwin' and _existing('entitlements.plist'):
    entitlements_path = 'entitlements.plist'

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NotionSync',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=entitlements_path,
    icon=icon_path,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NotionSync',
)

if sys.platform == 'darwin':
    app_icon = 'icon.icns' if _existing('icon.icns') else None
    app = BUNDLE(
        coll,
        name='NotionSync.app',
        icon=app_icon,
        bundle_identifier='com.fcanas.notionsync',
    )
