@echo off
setlocal
cd /d "%~dp0"

title Language Training Agent - Local Launcher

rem ---------------------------------------------------------------
rem  Single-process local launcher.
rem  The backend (FastAPI) serves the prebuilt frontend from
rem  frontend\dist on the same port, so no Vite dev server is needed.
rem  This avoids the known Windows Vite dev-server crash.
rem ---------------------------------------------------------------

if exist ".venv\Scripts\python.exe" (
  set "PYTHON=.venv\Scripts\python.exe"
) else (
  set "PYTHON=python"
)

echo [1/3] Checking whether the service is already running on port 8000...
curl --silent --fail http://127.0.0.1:8000/api/health >nul 2>&1
if not errorlevel 1 goto already_running

echo [2/3] Checking the frontend build...
if not exist "frontend\dist\index.html" (
  echo       frontend\dist is missing, building it now ^(requires Node.js^)...
  pushd frontend
  call npm install
  call npm run build
  popd
)

echo [3/3] Starting the service on http://127.0.0.1:8000 ...
start "Language Training Agent API" cmd /k ""%PYTHON%" -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000"

set "tries=0"
:wait
curl --silent --fail http://127.0.0.1:8000/api/health >nul 2>&1
if not errorlevel 1 goto open_browser
set /a tries+=1
if %tries% GEQ 40 goto open_browser
timeout /t 1 /nobreak >nul
goto wait

:already_running
echo       The service is already running. Opening the browser.
goto open_browser

:open_browser
start "" http://127.0.0.1:8000
echo.
echo Done. The app is available at http://127.0.0.1:8000
echo To stop it, close the "Language Training Agent API" window.
timeout /t 3 /nobreak >nul
exit /b 0
