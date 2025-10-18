@echo off
setlocal
cd /d "%~dp0"

echo === Pulling latest changes ===
git pull

if %errorlevel% neq 0 (
    echo.
    echo Git pull failed.
) else (
    echo.
    echo Repository updated successfully.
)

pause
