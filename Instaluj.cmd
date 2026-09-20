@echo off
setlocal
cd /d "%~dp0"
py -3.12 -m venv .venv
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m pip install -r requirements-lock.txt
if errorlevel 1 goto fail
echo Gotowe. Uruchom Uruchom.cmd.
pause
exit /b 0
:fail
echo Instalacja nie powiodla sie. Wymagany Python 3.12 64-bit i dostep do PyPI.
pause
exit /b 1

