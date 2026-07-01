@echo off
REM ============================================================
REM  GitNexus - Commit thay doi roi build/refresh index
REM  Chay file nay tu thu muc goc cua project
REM ============================================================

cd /d "%~dp0"

echo.
echo === Buoc 1: Git commit cac thay doi ===
git add -A

REM Chi commit khi co thay doi (staged)
git diff --cached --quiet
if errorlevel 1 (
    echo Co thay doi - dang commit...
    git commit -m "chore: auto-commit truoc khi gitnexus index"
) else (
    echo ============================================================
    echo  KHONG CO GI THAY DOI - khong can commit.
    echo  Van se chay lai GitNexus index ben duoi.
    echo ============================================================
)

echo.
echo === Buoc 2: GitNexus index project tai %CD% ===
echo.

npx gitnexus analyze %*

echo.
echo === Hoan tat. Ma thoat: %ERRORLEVEL% ===
pause
