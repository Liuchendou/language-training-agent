@echo off
setlocal
cd /d "%~dp0"

title Language Training Agent - Setup

rem ============================================================
rem  Minimal wrapper. All real logic lives in
rem  backend\scripts\setup_env.py -- see docs\transfer-guide.md
rem  for a step-by-step walkthrough.
rem
rem  This file is deliberately ASCII-only, matching start-local.bat:
rem  a .bat carrying non-ASCII text depends on the console code page
rem  and can be garbled or mis-parsed on some machines.
rem ============================================================

echo ============================================================
echo   Language Training Agent - Environment Setup
echo ============================================================
echo.
echo   Steps performed once: Python venv, backend dependencies,
echo   ffmpeg + speech model, frontend build.
echo   Roughly 460 MB of downloads. Details: docs\transfer-guide.md
echo.

set "PY="
where python >nul 2>&1
if not errorlevel 1 set "PY=python"

if not defined PY goto no_python

%PY% -c "import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 12) else 1)" >nul 2>&1
if errorlevel 1 goto bad_python

%PY% "backend\scripts\setup_env.py"
set "RC=%ERRORLEVEL%"

echo.
echo ------------------------------------------------------------
if "%RC%"=="0" (
  echo  Result: OK. Next: double-click start-local.bat
) else (
  echo  Result: exit code %RC% - see the messages above.
  echo  Walkthrough and troubleshooting: docs\transfer-guide.md
)
echo ------------------------------------------------------------
echo.
pause
exit /b %RC%

:no_python
echo [ERROR] Python was not found on this machine.
echo.
echo   Install Python 3.12 or newer:
echo     https://www.python.org/downloads/
echo   During setup, tick "Add python.exe to PATH".
echo   Then double-click setup.bat again.
echo.
pause
exit /b 1

:bad_python
echo [ERROR] Python 3.12 or newer is required (numpy 2.5.3 needs it).
echo.
echo   Detected version:
%PY% --version
echo.
echo   Install a newer Python: https://www.python.org/downloads/
echo.
pause
exit /b 1
