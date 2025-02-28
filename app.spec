# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Get additional hidden imports
hidden_imports = [
    'engineio.async_drivers.threading',
    'pkg_resources.py2_warn',
    'google.generativeai',
    'webview.platforms.winforms',
    'threading',
    'json',
    'time',
    're',
    'glob',
    'logging',
    'signal',
    'clr',
]

# Add Flask template folders, static files, etc.
datas = [
    ('templates', 'templates'),
    ('static', 'static'),
]

# Add any additional data files needed
datas += collect_data_files('flask_socketio')
datas += collect_data_files('engineio')
datas += collect_data_files('socketio')

a = Analysis(
    ['app.py'],
    pathex=[os.path.abspath(SPECPATH)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure, 
    a.zipped_data,
    cipher=block_cipher
)

# Modified EXE section to create a single file
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Codify',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,  # This is important for single-file mode
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='logo.ico',
    uac_admin=False,
)

# The COLLECT section is no longer needed and can be removed
# since we're creating a single executable