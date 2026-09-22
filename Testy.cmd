@echo off
setlocal
cd /d "%~dp0"
set "EC_VENV=%LOCALAPPDATA%\ElectroCount\py312-07"
if exist "%~dp0.runtime-path" set /p "EC_VENV="<"%~dp0.runtime-path"
"%EC_VENV%\Scripts\python.exe" -m pytest -q
pause
