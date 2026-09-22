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
"%EC_VENV%\Scripts\python.exe" tools\install_models.py
if errorlevel 1 (
    echo Instalacja modelu nie powiodla sie. Zachowaj komunikat bledu.
    pause
    exit /b 1
)
pause
