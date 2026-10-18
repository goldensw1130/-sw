@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1
cd /d "%~dp0" || goto :folder_error
title ShortCompass v2.47 Launcher

if defined LOCALAPPDATA (
  set "LOG_DIR=%LOCALAPPDATA%\ShortCompass\logs"
) else (
  set "LOG_DIR=%TEMP%\ShortCompass\logs"
)
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
set "LOG_FILE=%LOG_DIR%\start-shortcompass.log"
echo.>>"%LOG_FILE%"
echo [%date% %time%] Start launcher v2.47 started>>"%LOG_FILE%"

if not exist "%~dp0ShortsCompass.html" goto :missing_html
if not exist "%~dp0ShortCompassServer.py" goto :missing_server
if not exist "%~dp0Start_ShortCompass_Server.bat" goto :missing_launcher

rem Check a currently running local server with a simple status code.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "try { $r=Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 2; if ($r.ok -and $r.service -eq 'ShortCompass local helper' -and [string]$r.version -eq '2.47') { exit 0 }; exit 2 } catch { exit 1 }" >nul 2>&1
set "HEALTH_CODE=%ERRORLEVEL%"
if "%HEALTH_CODE%"=="0" goto :open_browser
if "%HEALTH_CODE%"=="2" goto :old_server

echo [1/3] Starting local server in a separate console.
start "ShortCompass Local Server v2.47" /D "%~dp0" "%ComSpec%" /k call Start_ShortCompass_Server.bat
if errorlevel 1 goto :launch_error

echo [2/3] Waiting for the local server health check (maximum 30 seconds).
set "WAIT_COUNT=0"
:wait_for_server
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "try { $r=Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 1; if ($r.ok -and $r.service -eq 'ShortCompass local helper' -and [string]$r.version -eq '2.47') { exit 0 } } catch { }; exit 1" >nul 2>&1
if not errorlevel 1 goto :open_browser
set /a WAIT_COUNT+=1
if %WAIT_COUNT% GEQ 30 goto :health_failed
timeout /t 1 /nobreak >nul
goto :wait_for_server

:open_browser
echo [3/3] Local server is healthy. Opening browser.
echo [%date% %time%] Browser opened after health check>>"%LOG_FILE%"
start "" "http://127.0.0.1:8765/ShortsCompass.html"
echo.
echo ShortCompass v2.47 launch request completed.
echo Keep the separate server console open while using local search, AI proxy, and updater features.
echo Diagnostic log: "%LOG_FILE%"
pause >nul
exit /b 0

:old_server
echo An older or different service is already using http://127.0.0.1:8765/.
echo Close the old ShortCompass server console with Ctrl+C, then run this launcher again.
echo Diagnostic log: "%LOG_FILE%"
pause
exit /b 1

:health_failed
echo ERROR: ShortCompass v2.47 did not pass the health check within 30 seconds.
echo The separate server window should remain open and show its own error.
echo Diagnostic log: "%LOG_FILE%"
echo Last log entries:
powershell.exe -NoLogo -NoProfile -Command "Get-Content -LiteralPath '%LOG_FILE%' -Tail 60 -ErrorAction SilentlyContinue"
pause
exit /b 1

:launch_error
echo ERROR: Could not start the separate server console.
goto :show_log_error

:missing_html
echo ERROR: ShortsCompass.html is missing. Extract the entire release ZIP into a new folder.
goto :show_log_error
:missing_server
echo ERROR: ShortCompassServer.py is missing. Extract the entire release ZIP into a new folder.
goto :show_log_error
:missing_launcher
echo ERROR: Start_ShortCompass_Server.bat is missing. Extract the entire release ZIP into a new folder.
goto :show_log_error
:folder_error
echo ERROR: Could not enter the program folder. Run this file from the extracted folder.
goto :show_log_error

:show_log_error
echo [%date% %time%] Launcher failure. Current path: %CD%>>"%LOG_FILE%"
echo Diagnostic log: "%LOG_FILE%"
pause
exit /b 1
