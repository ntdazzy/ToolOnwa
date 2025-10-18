@echo off
setlocal
cd /d "%~dp0"

:: Ưu tiên Python 3.11 nếu có, fallback về python chuẩn
set "PY_CMD="
where py >nul 2>nul && (
    py -3.11 -V >nul 2>nul && set "PY_CMD=py -3.11"
) 
if not defined PY_CMD (
    where python >nul 2>nul && set "PY_CMD=python"
)
if not defined PY_CMD (
    echo Can not find Python interpreter on PATH.
    pause
    exit /b 1
)

:: Tạo hoặc sử dụng lại venv
if not exist ".venv" (
    %PY_CMD% -m venv .venv || goto :e
)
call .venv\Scripts\activate.bat

python -m pip install --upgrade pip
if exist requirements.txt (
    python -m pip install -r requirements.txt
)
:: Đảm bảo PyInstaller và các driver cần thiết luôn được cài
python -m pip install --upgrade pyinstaller oracledb cx-Oracle

:: Dọn build cũ
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist ToolONWA.spec del /q ToolONWA.spec

:: Build 1 file exe + icon + kèm data
python -m PyInstaller main.py ^
  --onefile ^
  --clean ^
  --name "ToolONWA" ^
  --noconsole ^
  --icon "icons\logo.ico" ^
  --add-data "configs;configs" ^
  --add-data "ora;ora" ^
  --add-data "fonts;fonts" ^
  --add-data "icons;icons" ^
  --add-data "screen;screen" ^
  --hidden-import screen.DB.edit_connection ^
  --hidden-import screen.DB.cmd_sql_plus ^
  --hidden-import screen.DB.backup ^
  --hidden-import screen.DB.compare ^
  --hidden-import screen.DB.db_utils ^
  --hidden-import screen.DB.insert ^
  --hidden-import screen.DB.update ^
  --hidden-import screen.DB.widgets ^
  --hidden-import screen.DB.template_dialog ^
  --hidden-import screen.General.bikipvocong ^
  --hidden-import screen.General.history_window ^
  --hidden-import screen.General.rdsinfo ^
  --hidden-import screen.General.tailieu ^
  --hidden-import screen.MU.log_viewer ^
  --hidden-import core.i18n ^
  --hidden-import core.history ^
  --hidden-import core.templates

echo.
echo === DONE ===
echo File: dist\ToolONWA.exe
pause
exit /b 0

:e
echo Failed to create venv. Check Python installation.
pause
exit /b 1
