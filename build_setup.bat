@echo off
REM ================================================================
REM  Tao file cai dat SnagTin-Setup-<ver>.exe (installer Inno Setup)
REM  Goi scripts/build_installer.py chay full pipeline:
REM    1) sinh icon (neu chua co)
REM    2) PyInstaller build onedir  -> dist\SnagTin\
REM    3) don file onefile cu       -> dist\SnagTin.exe (neu con)
REM    4) Inno Setup (ISCC)         -> dist\SnagTin-Setup-<ver>.exe
REM
REM  Yeu cau:
REM    - da chay  pip install -r requirements.txt  va  pip install pyinstaller
REM    - da cai Inno Setup 6 (ISCC.exe). Tai free tai https://jrsoftware.org/isdl.php
REM
REM  Tuy chon (truyen vao .bat se chuyen tiep cho script python):
REM    build_setup.bat                 full pipeline
REM    build_setup.bat --skip-build    dung dist\SnagTin\ san co, khoi build lai
REM    build_setup.bat --iss-only      chi chay buoc ISCC (nhanh nhat de thu)
REM ================================================================
setlocal
cd /d "%~dp0"

echo === Tao SnagTin Setup.exe ===
python scripts\build_installer.py %*
if errorlevel 1 (
  echo.
  echo LOI: Build that bai hoac chua cai Inno Setup. Xem log o tren.
  endlocal
  pause
  exit /b 1
)

echo.
echo Hoan tat. File cai dat nam o thu muc:  dist\
endlocal
pause
