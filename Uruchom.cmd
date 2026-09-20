@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0.venv\Scripts\pythonw.exe" (
    start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0launch.py" %*
    exit /b
)
set "PY=%~dp0..\..\work\.venv\Scripts\pythonw.exe"
if exist "%PY%" (
    start "" "%PY%" "%~dp0launch.py" %*
    exit /b
)
echo Najpierw uruchom Instaluj.cmd.
pause
