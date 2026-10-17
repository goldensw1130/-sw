@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1
cd /d "%~dp0" || goto :folder_error
title 숏폼 나침반 로컬 서버 v2.46

if defined LOCALAPPDATA (
  set "LOG_DIR=%LOCALAPPDATA%\ShortCompass\logs"
) else (
  set "LOG_DIR=%TEMP%\ShortCompass\logs"
)
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
set "LOG_FILE=%LOG_DIR%\start-shortcompass.log"
echo.>>"%LOG_FILE%"
echo [%date% %time%] Server launcher v2.46 started>>"%LOG_FILE%"

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

echo 오류: Python 3 실행 파일을 찾지 못했습니다.
echo Python 3을 설치하거나 Windows 앱 실행 별칭을 확인하세요.
echo 로그 파일: "%LOG_FILE%"
echo.
powershell.exe -NoLogo -NoProfile -Command "Get-Content -LiteralPath '%LOG_FILE%' -Tail 40 -ErrorAction SilentlyContinue"
pause
exit /b 1

:run_py
echo Python launcher를 통해 ShortCompassServer.py를 실행합니다.
echo 로그 파일: "%LOG_FILE%"
py -3 -u "%~dp0ShortCompassServer.py" >>"%LOG_FILE%" 2>&1
set "SERVER_EXIT_CODE=%ERRORLEVEL%"
goto :server_exited

:run_python
echo python 명령으로 ShortCompassServer.py를 실행합니다.
echo 로그 파일: "%LOG_FILE%"
python -u "%~dp0ShortCompassServer.py" >>"%LOG_FILE%" 2>&1
set "SERVER_EXIT_CODE=%ERRORLEVEL%"
goto :server_exited

:server_exited
echo [%date% %time%] Server process exited with code %SERVER_EXIT_CODE%>>"%LOG_FILE%"
echo.
echo 로컬 서버가 종료되었습니다. 종료 코드: %SERVER_EXIT_CODE%
echo 로그 파일: "%LOG_FILE%"
echo 마지막 오류 기록:
powershell.exe -NoLogo -NoProfile -Command "Get-Content -LiteralPath '%LOG_FILE%' -Tail 60 -ErrorAction SilentlyContinue"
echo.
echo 오류 확인을 위해 이 서버 창은 자동으로 닫히지 않습니다.
pause
exit /b %SERVER_EXIT_CODE%

:missing_server
echo 오류: ShortCompassServer.py 파일을 찾을 수 없습니다.
echo 로그 파일: "%LOG_FILE%"
pause
exit /b 1

:folder_error
echo 오류: 프로그램 폴더로 이동하지 못했습니다.
echo 압축을 푼 폴더 안에서 이 파일을 실행하세요.
pause
exit /b 1
