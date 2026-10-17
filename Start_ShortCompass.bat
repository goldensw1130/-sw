@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title 숏폼 나침반 로컬 검색 도우미
if not exist "%~dp0ShortsCompass.html" (
  echo 오류: ShortsCompass.html 파일을 찾을 수 없습니다.
  pause
  exit /b 1
)
where py >nul 2>nul
if %errorlevel%==0 (
  echo 숏폼 나침반 로컬 검색 서버를 시작합니다.
  start "숏폼 나침반 로컬 서버" /min cmd.exe /k "cd /d ""%~dp0"" && py -3 ShortCompassServer.py"
  timeout /t 2 >nul
  start "" "http://127.0.0.1:8765/ShortsCompass.html"
  echo 앱을 열었습니다. 이 창은 닫아도 되지만 로컬 서버 창은 검색 기능을 위해 유지하세요.
  echo 서버를 종료하려면 별도 서버 창에서 Ctrl+C를 누르세요.
  pause
  exit /b 0
)
where python >nul 2>nul
if %errorlevel%==0 (
  echo 숏폼 나침반 로컬 검색 서버를 시작합니다.
  start "숏폼 나침반 로컬 서버" /min cmd.exe /k "cd /d ""%~dp0"" && python ShortCompassServer.py"
  timeout /t 2 >nul
  start "" "http://127.0.0.1:8765/ShortsCompass.html"
  echo 앱을 열었습니다. 로컬 검색 기능은 Python 서버가 실행 중일 때만 작동합니다.
  pause
  exit /b 0
)
echo Python 3을 찾지 못했습니다. 자동 웹 검색은 사용할 수 없으며 기본 HTML 앱만 엽니다.
start "" "%~dp0ShortsCompass.html"
echo 자동 검색을 사용하려면 Python 3을 설치한 뒤 이 파일을 다시 실행하세요.
pause
endlocal
