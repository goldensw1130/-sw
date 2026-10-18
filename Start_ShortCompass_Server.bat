@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1
cd /d "%~dp0" || goto :folder_error
title ShortCompass Local Server v2.47

if defined LOCALAPPDATA (
  set "LOG_DIR=%LOCALAPPDATA%\ShortCompass\logs"
) else (
  set "LOG_DIR=%TEMP%\ShortCompass\logs"
)
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
set "LOG_FILE=%LOG_DIR%\start-shortcompass.log"
echo.>>"%LOG_FILE%"
echo [%date% %time%] Server launcher v2.47 started>>"%LOG_FILE%"

if not exist "%~dp0ShortCompassServer.py" goto :missing_server

where py >nul 2>&1
if not errorlevel 1 (
  py -3 --version >>"%LOG_FILE%" 2>&1
  if not errorlevel 1 goto :run_py
)
where python >nul 2>&1
if not errorlevel 1 (
  python --version >>"%LOG_FILE%" 2>&1
  if not errorlevel 1 goto :run_python
)

echo ERROR: Python 3 could not be found. Install Python 3 or check Windows app execution aliases.
echo Diagnostic log: "%LOG_FILE%"
powershell.exe -NoLogo -NoProfile -Command "Get-Content -LiteralPath '%LOG_FILE%' -Tail 40 -ErrorAction SilentlyContinue"
pause
exit /b 1

:run_py
echo Running server through the Python launcher. Keep this console open.
echo Diagnostic log: "%LOG_FILE%"
py -3 -u "%~dp0ShortCompassServer.py" >>"%LOG_FILE%" 2>&1
set "SERVER_EXIT_CODE=%ERRORLEVEL%"
goto :server_exited

:run_python
echo Running server through python.exe. Keep this console open.
echo Diagnostic log: "%LOG_FILE%"
python -u "%~dp0ShortCompassServer.py" >>"%LOG_FILE%" 2>&1
set "SERVER_EXIT_CODE=%ERRORLEVEL%"
goto :server_exited

:server_exited
echo [%date% %time%] Server process exited with code %SERVER_EXIT_CODE%>>"%LOG_FILE%"
echo.
echo The local server has exited. Exit code: %SERVER_EXIT_CODE%
echo Diagnostic log: "%LOG_FILE%"
echo Last log entries:
powershell.exe -NoLogo -NoProfile -Command "Get-Content -LiteralPath '%LOG_FILE%' -Tail 60 -ErrorAction SilentlyContinue"
echo This window is intentionally kept open so the error remains visible.
pause
exit /b %SERVER_EXIT_CODE%

:missing_server
echo ERROR: ShortCompassServer.py is missing from this folder.
echo Diagnostic log: "%LOG_FILE%"
pause
exit /b 1

:folder_error
echo ERROR: Could not enter program folder. Run this file from the extracted folder.
pause
exit /b 1
