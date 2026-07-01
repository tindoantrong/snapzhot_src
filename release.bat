@echo off
REM ================================================================
REM  Sinh latest.json tu __version__ va (tuy chon) build Setup.exe
REM
REM  Su dung:
REM    release.bat                          sinh manifest + full build
REM    release.bat --skip-build             chi sinh manifest, khong build
REM    release.bat --iss-only               manifest + chi buoc ISCC
REM    release.bat --notes "Ban va loi X"   ghi de notes manifest
REM    release.bat --publish                sinh manifest + build + tu day len GitHub
REM
REM  Sau khi chay xong (khong co --publish), xem checklist de upload 2 artifact len GitHub.
REM ================================================================
setlocal
cd /d "%~dp0"

echo === Sinh latest.json va build SnagTin release ===
python scripts\make_release.py %*
if errorlevel 1 (
  echo.
  echo LOI: make_release that bai. Xem log o tren.
  endlocal
  pause
  exit /b 1
)

echo.
echo Hoan tat. Xem checklist o tren de upload len GitHub (hoac da publish neu co --publish).
endlocal
pause
