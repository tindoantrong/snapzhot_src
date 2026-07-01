@echo off
REM ================================================================
REM  Build SnagTin thanh file EXE chay doc lap tren Windows
REM  Dong goi TU FILE SPEC (SnagTin.spec) de dung dung cau hinh:
REM    - icon EXE + bundle bo icon (assets/icon.ico, icon.png, icons/)
REM    - hidden imports, exclude cac Qt module nang, collect ffmpeg/audio
REM  Moi tuy chon nam trong SnagTin.spec; sua o do thay vi them co dong lenh.
REM  Yeu cau: da chay  pip install -r requirements.txt  va  pip install pyinstaller
REM ================================================================
setlocal

echo [1/2] Cai PyInstaller (neu chua co)...
pip install pyinstaller

echo [2/2] Dong goi EXE tu SnagTin.spec...
REM  Build tu spec: pyinstaller BO QUA cac co dong lenh ve build (ten/onefile/
REM  hidden-import/exclude/icon...) vi tat ca da khai bao trong spec.
pyinstaller --noconfirm --clean SnagTin.spec
if errorlevel 1 (
  echo.
  echo LOI: Dong goi that bai. Xem log o tren.
  endlocal
  pause
  exit /b 1
)

echo.
echo Hoan tat. File EXE nam o:  dist\SnagTin.exe
echo Luu y: EXE onefile (~150MB do chua ffmpeg) khoi dong cham lan dau vi phai
echo        giai nen ra thu muc tam. Muon nhanh hon: sua SnagTin.spec sang onedir.
endlocal
pause
