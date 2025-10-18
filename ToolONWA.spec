# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_submodules

datas = [('configs', 'configs'), ('ora', 'ora'), ('fonts', 'fonts'), ('icons', 'icons'), ('screen', 'screen')]
hiddenimports = ['screen.DB.edit_connection', 'screen.DB.cmd_sql_plus', 'screen.DB.backup', 'screen.DB.compare', 'screen.DB.db_utils', 'screen.DB.insert', 'screen.DB.update', 'screen.DB.widgets', 'screen.DB.template_dialog', 'screen.General.bikipvocong', 'screen.General.history_window', 'screen.General.rdsinfo', 'screen.General.tailieu', 'screen.MU.log_viewer', 'core.i18n', 'core.history', 'core.templates', 'cryptography', 'cryptography.x509']
datas += collect_data_files('cryptography')
hiddenimports += collect_submodules('cryptography')


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='ToolONWA',
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
    icon=['icons\\logo.ico'],
)
