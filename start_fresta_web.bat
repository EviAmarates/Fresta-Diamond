@echo off
setlocal
cd /d "%~dp0"

if not defined FRESTA_MODEL set "FRESTA_MODEL=openai/gpt-oss-20b"
if not defined FRESTA_LLM_URL set "FRESTA_LLM_URL=http://127.0.0.1:1234"
if not defined FRESTA_WEB_PORT set "FRESTA_WEB_PORT=8765"

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found on PATH.
  echo Install Python 3.10+ and try again.
  pause
  exit /b 1
)

if not exist ".\local-web-data" mkdir ".\local-web-data"

echo Starting Fresta Diamond Web...
echo Model: %FRESTA_MODEL%
echo Local model endpoint: %FRESTA_LLM_URL%
echo Close this window to stop the Web.
echo.

python run_web.py ^
  --data-root ".\local-web-data" ^
  --host "127.0.0.1" ^
  --port "%FRESTA_WEB_PORT%" ^
  --base-url "%FRESTA_LLM_URL%" ^
  --model "%FRESTA_MODEL%" ^
  --open-browser

echo.
echo Fresta Diamond Web stopped.
pause
