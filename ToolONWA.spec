# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('configs', 'configs'), ('ora', 'ora'), ('fonts', 'fonts'), ('icons', 'icons'), ('screen', 'screen')],
    hiddenimports=['screen.DB.edit_connection', 'screen.DB.cmd_sql_plus', 'screen.DB.backup', 'screen.DB.compare', 'screen.DB.db_utils', 'screen.DB.insert', 'screen.DB.update', 'screen.DB.widgets', 'screen.General.bikipvocong', 'screen.General.rdsinfo', 'screen.General.tailieu', 'screen.MU.log_viewer', 'core.i18n', 'core.history', 'core.templates'],
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
