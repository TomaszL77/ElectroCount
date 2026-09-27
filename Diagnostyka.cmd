@echo off
setlocal
cd /d "%~dp0"
set "EC_VENV=%LOCALAPPDATA%\ElectroCount\py312-07"
if exist "%~dp0.runtime-path" set /p "EC_VENV="<"%~dp0.runtime-path"
if not exist "%EC_VENV%\Scripts\python.exe" (
    echo Najpierw uruchom Instaluj.cmd.
    pause
    exit /b 1
)
set "PYTHONPATH=%~dp0src"
"%EC_VENV%\Scripts\python.exe" -m electrocount.debug_cli --self-test --engine-mode hybrid_base
pause
