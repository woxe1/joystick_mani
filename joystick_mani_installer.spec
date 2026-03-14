# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('C:\\Users\\Vladimir\\prod\\joystick_mani\\clean\\freecad_hid_udp_bridge.py', '.'), ('C:\\Users\\Vladimir\\prod\\joystick_mani\\clean\\freecad_udp_orbit_autostart.py', '.'), ('C:\\Users\\Vladimir\\prod\\joystick_mani\\clean\\freecad_udp_orbit_macro.py', '.'), ('C:\\Users\\Vladimir\\prod\\joystick_mani\\tools\\freecad_hid_calibration.json', '.')]
binaries = []
hiddenimports = ['hid']
tmp_ret = collect_all('hid')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['C:\\Users\\Vladimir\\prod\\joystick_mani\\clean\\installer.py'],
    pathex=[],
    binaries=binaries,
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
    name='joystick_mani_installer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
