@echo off
setlocal
cd /d "%~dp0"

:: Ưu tiên Python 3.11 nếu có
where py >nul 2>nul && (py -3.11 -V >nul 2>nul && set "PY=py -3.11") || (set "PY=python")

:: Tạo venv
%PY% -m venv venv || goto :e
call venv\Scripts\activate.bat

python -m pip install --upgrade pip
pip install pyinstaller

:: Build 1 file exe + icon + kèm data
pyinstaller main.py ^
  --onefile ^
  --name "ToolONWA" ^
  --noconsole ^
  --icon "icons\logo.ico" ^
  --add-data "configs;configs" ^
  --add-data "ora;ora" ^
  --add-data "fonts;fonts" ^
  --add-data "icons;icons" ^
  --add-data "screen;screen" ^
  --hidden-import screen.DB.edit_connection ^
  --hidden-import screen.DB.cmd_sql_plus

echo.
echo === DONE ===
echo File: dist\ToolONWA.exe
pause
exit /b 0

:e
echo Failed to create venv. Check Python installation.
pause
exit /b 1
