@echo off
setlocal EnableExtensions
chcp 65001 >nul 2>&1
cd /d "%~dp0" || goto :folder_error
title 숏폼 나침반 v2.46 실행 관리자

if defined LOCALAPPDATA (
  set "LOG_DIR=%LOCALAPPDATA%\ShortCompass\logs"
) else (
  set "LOG_DIR=%TEMP%\ShortCompass\logs"
)
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1
set "LOG_FILE=%LOG_DIR%\start-shortcompass.log"
echo [%date% %time%] Start launcher v2.46 started>>"%LOG_FILE%"

if not exist "%~dp0ShortsCompass.html" goto :missing_html
if not exist "%~dp0ShortCompassServer.py" goto :missing_server
if not exist "%~dp0Start_ShortCompass_Server.bat" goto :missing_launcher

rem Reuse a healthy ShortCompass server already running on localhost.
set "RUNNING_VERSION="
for /f "usebackq delims=" %%V in (`powershell.exe -NoLogo -NoProfile -Command "try { $r=Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 2; if ($r.ok -and $r.service -eq 'ShortCompass local helper') { [Console]::WriteLine([string]$r.version) } } catch { }" 2^>nul`) do set "RUNNING_VERSION=%%V"
if defined RUNNING_VERSION goto :existing_server

echo [1/3] 로컬 서버를 시작합니다.
start "숏폼 나침반 로컬 서버 v2.46" "%~dp0Start_ShortCompass_Server.bat"
if errorlevel 1 goto :launch_error

echo [2/3] 서버 상태를 확인합니다. 잠시 기다려 주세요.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$deadline=(Get-Date).AddSeconds(20); do { try { $r=Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 1; if ($r.ok -and $r.service -eq 'ShortCompass local helper' -and [string]$r.version -eq '2.46') { exit 0 } } catch { }; Start-Sleep -Milliseconds 500 } while ((Get-Date) -lt $deadline); exit 1" >nul 2>&1
if errorlevel 1 goto :health_failed

echo [3/3] 서버 정상 응답을 확인했습니다. 브라우저를 엽니다.
start "" "http://127.0.0.1:8765/ShortsCompass.html"
echo.
echo 숏폼 나침반 v2.46이 실행되었습니다.
echo 로컬 서버 창을 닫으면 앱 안의 로컬 검색, AI 프록시, 업데이트 기능이 중단됩니다.
echo 서버 로그: "%LOG_FILE%"
echo 이 안내 창은 아무 키나 누르면 닫힙니다.
pause >nul
exit /b 0

:existing_server
if "%RUNNING_VERSION%"=="2.46" goto :open_existing
 echo 기존 숏폼 나침반 서버 버전 %RUNNING_VERSION% 이 이미 실행 중입니다.
 echo 이전 서버 창에서 Ctrl+C로 종료한 다음 Start_ShortCompass.bat을 다시 실행하세요.
 echo 로그: "%LOG_FILE%"
 pause
 exit /b 1

:open_existing
echo 숏폼 나침반 v2.46 서버가 이미 실행 중입니다. 기존 서버를 사용합니다.
start "" "http://127.0.0.1:8765/ShortsCompass.html"
echo 서버 로그: "%LOG_FILE%"
pause >nul
exit /b 0

:health_failed
echo 오류: 20초 안에 숏폼 나침반 로컬 서버의 정상 응답을 확인하지 못했습니다.
echo 서버가 실행되지 않았거나 8765 포트를 다른 프로그램이 사용 중일 수 있습니다.
echo 로그 파일: "%LOG_FILE%"
if exist "%LOG_FILE%" powershell.exe -NoLogo -NoProfile -Command "Get-Content -LiteralPath '%LOG_FILE%' -Tail 60 -ErrorAction SilentlyContinue"
echo 이 창은 오류 확인을 위해 열려 있습니다.
pause
exit /b 1

:launch_error
echo 오류: 서버 시작 창을 열지 못했습니다.
goto :show_log_error

:missing_html
echo 오류: ShortsCompass.html 파일이 없습니다. ZIP을 새 폴더에 다시 압축 해제하세요.
goto :show_log_error
:missing_server
echo 오류: ShortCompassServer.py 파일이 없습니다. ZIP 전체 압축 해제 여부를 확인하세요.
goto :show_log_error
:missing_launcher
echo 오류: Start_ShortCompass_Server.bat 파일이 없습니다. v2.46 ZIP 전체를 새 폴더에 압축 해제하세요.
goto :show_log_error
:folder_error
echo 오류: 프로그램 폴더로 이동하지 못했습니다. 압축 해제 위치와 권한을 확인하세요.
goto :show_log_error

:show_log_error
echo [%date% %time%] Launcher failure. Current path: %CD%>>"%LOG_FILE%"
echo 로그 파일: "%LOG_FILE%"
echo 이 창은 오류 확인을 위해 열려 있습니다.
pause
exit /b 1
