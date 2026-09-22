@echo off
setlocal
cd /d "%~dp0"
set "EC_VENV=%LOCALAPPDATA%\ElectroCount\py312-06"
if defined ELECTROCOUNT_RUNTIME_DIR set "EC_VENV=%ELECTROCOUNT_RUNTIME_DIR%"
where py >nul 2>nul
if errorlevel 1 (
    python -c "import sys; assert sys.version_info[:2]==(3,12)" >nul 2>nul
    if errorlevel 1 goto fail
    python -m venv "%EC_VENV%"
) else (
    py -3.12 -m venv "%EC_VENV%"
)
if errorlevel 1 goto fail
"%EC_VENV%\Scripts\python.exe" -m pip install --only-binary=:all: --require-hashes -r requirements-win.lock
if errorlevel 1 goto fail
"%EC_VENV%\Scripts\python.exe" -m pip check
if errorlevel 1 goto fail
"%EC_VENV%\Scripts\python.exe" check_runtime.py
if errorlevel 1 goto fail
set "PYTHONPATH=%~dp0src"
"%EC_VENV%\Scripts\python.exe" -m electrocount.debug_cli --self-test
if errorlevel 1 goto fail
>"%~dp0.runtime-path" echo %EC_VENV%
echo Gotowe. Test diagnostyczny PASS. Uruchom Uruchom.cmd.
pause
exit /b 0
:fail
echo Instalacja lub test nie powiodly sie. Wymagany Python 3.12 64-bit i dostep do PyPI.
echo Zachowaj komunikat bledu. Instalator nie uznaje niezgodnego srodowiska za gotowe.
pause
exit /b 1
