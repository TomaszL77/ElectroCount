@echo off
setlocal
cd /d "%~dp0"
set "EC_VENV=%LOCALAPPDATA%\ElectroCount\py312-07"
if exist "%~dp0.runtime-path" set /p "EC_VENV="<"%~dp0.runtime-path"
if not exist "%EC_VENV%\Scripts\pythonw.exe" goto missing
"%EC_VENV%\Scripts\python.exe" "%~dp0check_runtime.py" > "%TEMP%\ElectroCount-runtime-check.txt" 2>&1
if errorlevel 1 (
    echo Wersje bibliotek nie pasuja do tej wersji ElectroCount. Uruchom Instaluj.cmd.
    type "%TEMP%\ElectroCount-runtime-check.txt"
    pause
    exit /b 1
)
start "ElectroCount" "%EC_VENV%\Scripts\pythonw.exe" "%~dp0launch.py" %*
exit /b 0
:missing
echo Najpierw uruchom Instaluj.cmd. Aplikacja korzysta tylko z runtime w krotkiej sciezce.
pause
exit /b 1
