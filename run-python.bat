@echo off
setlocal
if "%SCHEDULER_DATA%"=="" set SCHEDULER_DATA=C:\scheduler
set API_DIR=%SCHEDULER_DATA%\app\obs-scheduler-api
set VENV=%SCHEDULER_DATA%\.venv

if not exist "%VENV%\Scripts\activate.bat" (
  echo Virtual env not found. Run install-python.ps1 first.
  exit /b 1
)

rem Configure OBS websocket connection (leave empty to use config.json)
if "%OBS_HOST%"=="" set OBS_HOST=127.0.0.1
if "%OBS_PORT%"=="" set OBS_PORT=4455

pushd "%API_DIR%"
call "%VENV%\Scripts\activate.bat"
echo Starting OBS Scheduler API on http://localhost:8080 (Ctrl+C to stop)...
uvicorn app:app --port 8080
popd
endlocal
