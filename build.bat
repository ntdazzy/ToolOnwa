@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

:: Ưu tiên Python 3.11 nếu có, fallback về python mặc định
set "PY_CMD="
where py >nul 2>nul && (
    py -3.11 -V >nul 2>nul && set "PY_CMD=py -3.11"
)
if not defined PY_CMD (
    where python >nul 2>nul && set "PY_CMD=python"
)
if not defined PY_CMD (
    echo Khong tim thay Python tren PATH. Vui long cai dat Python 3.11+.
    pause
    exit /b 1
)

:: Tao virtualenv neu chua co
if not exist ".venv" (
    %PY_CMD% -m venv .venv || goto :venv_error
)
call ".venv\Scripts\activate.bat"

python -m pip install --upgrade pip

set "PIP_FAIL="
if exist requirements.txt (
    python -m pip install -r requirements.txt || set "PIP_FAIL=1"
)

:: Dam bao cac goi quan trong duoc cai dat du
python -m pip install --upgrade pyinstaller oracledb requests cryptography

:: Chi cai cx-Oracle khi ho tro (Python <= 3.12) va toolchain san sang
call :maybe_install_cxoracle

:: Don sach build cu
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist ToolONWA.spec del /q ToolONWA.spec

:: Build exe
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
  --hidden-import core.templates ^
  --hidden-import cryptography

echo.
echo === DONE ===
echo File: dist\ToolONWA.exe
pause
exit /b 0

:venv_error
echo Failed to create virtual environment. Kiem tra lai cai dat Python.
pause
exit /b 1

:maybe_install_cxoracle
for /f "delims=" %%v in ('python -c "import sys; print(sys.version_info.major)"') do set "PY_MAJOR=%%v"
for /f "delims=" %%v in ('python -c "import sys; print(sys.version_info.minor)"') do set "PY_MINOR=%%v"
if not defined PY_MAJOR exit /b 0

set "SKIP_CXO="
if !PY_MAJOR! GTR 3 set "SKIP_CXO=1"
if !PY_MAJOR! EQU 3 if !PY_MINOR! GEQ 13 set "SKIP_CXO=1"

if defined SKIP_CXO (
    echo Bo qua cai dat cx-Oracle cho Python !PY_MAJOR!.!PY_MINOR! (khong co wheel san).
) else (
    python -m pip install --upgrade cx-Oracle || (
        echo.
        echo WARNING: Khong the cai cx-Oracle. Nen cai "Microsoft C++ Build Tools" neu can su dung thick mode.
    )
)
exit /b 0
