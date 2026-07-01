# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_submodules
from PyInstaller.utils.hooks import collect_all
from PyInstaller.utils.hooks import copy_metadata

datas = []
binaries = []

# Asset icon (bundle vào app; icon EXE nếu có file .ico).
if os.path.exists('assets/icon.png'):
    datas += [('assets/icon.png', 'assets')]
# Bộ icon đa độ phân giải (assets/icons/icon_<n>.png) cho QIcon sắc nét mọi size.
if os.path.isdir('assets/icons'):
    datas += [('assets/icons', 'assets/icons')]
_icon_ico = 'assets/icon.ico' if os.path.exists('assets/icon.ico') else None
if _icon_ico:
    datas += [('assets/icon.ico', 'assets')]

hiddenimports = ['keyboard', 'win32gui', 'win32con', 'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets']
datas += copy_metadata('imageio')
hiddenimports += collect_submodules('mss')
hiddenimports += collect_submodules('imageio')
tmp_ret = collect_all('imageio_ffmpeg')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('sounddevice')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('soundfile')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineQuick', 'PySide6.QtWebEngine', 'PySide6.QtWebChannel', 'PySide6.QtWebSockets', 'PySide6.Qt3DCore', 'PySide6.Qt3DRender', 'PySide6.QtCharts', 'PySide6.QtDataVisualization', 'PySide6.QtQuick', 'PySide6.QtQuick3D', 'PySide6.QtQml', 'PySide6.QtPdf', 'PySide6.QtPositioning', 'PySide6.QtSql', 'PySide6.QtDesigner', 'PySide6.QtBluetooth', 'PySide6.QtSensors', 'PySide6.QtTest'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# onedir: EXE chỉ chứa loader + scripts, binaries/datas để COLLECT gom vào thư mục
# → khởi động NHANH hơn onefile (không giải nén tạm mỗi lần chạy).
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SnagTin',
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
    icon=_icon_ico,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SnagTin',
)
