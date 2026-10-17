@echo off
setlocal EnableExtensions
rem Keep the same console open even if PowerShell exits before displaying a prompt.
if /i not "%SHORTCOMPASS_KEEP_OPEN_246%"=="1" (
  set "SHORTCOMPASS_KEEP_OPEN_246=1"
  cmd.exe /k ""%~f0" %*"
  exit /b
)
set "SHORTCOMPASS_KEEP_OPEN_246="
chcp 65001 >nul
title ShortCompass GitHub Auto Release Setup
if not defined LOCALAPPDATA set "LOCALAPPDATA=%USERPROFILE%\AppData\Local"
set "LOGDIR=%LOCALAPPDATA%\ShortCompass\logs"
set "LOGFILE=%LOGDIR%\github-autorelease-setup.log"
if not exist "%LOGDIR%" mkdir "%LOGDIR%" >nul 2>nul
if not exist "%LOGDIR%" set "LOGFILE=%~dp0github-autorelease-setup.log"
echo.>>"%LOGFILE%"
echo ================================================================>>"%LOGFILE%"
echo [%date% %time%] v2.46 launcher started>>"%LOGFILE%"
echo ================================================================
echo ShortCompass GitHub Auto Release Setup - v2.46
echo Log file: "%LOGFILE%"
echo Repository: https://github.com/goldensw1130/-sw
echo 기존 저장소도 README/.gitignore와 .github/workflows/release.yml만 있으면 이어서 설정할 수 있습니다.
echo.
echo This window is intentionally kept open. Do not close it while setup is running.
echo If setup fails, the error and log will remain visible.
echo.
if not exist "%~dp0Setup_GitHub_AutoRelease.ps1" (
  echo ERROR: Setup_GitHub_AutoRelease.ps1 is missing from this folder.
  >>"%LOGFILE%" echo ERROR: Setup_GitHub_AutoRelease.ps1 is missing from this folder.
  set "RC=2"
  goto :failed
)
where powershell.exe >nul 2>nul
if errorlevel 1 (
  echo ERROR: Windows PowerShell 5.1 was not found.
  >>"%LOGFILE%" echo ERROR: Windows PowerShell 5.1 was not found.
  set "RC=3"
  goto :failed
)
for /f "delims=" %%V in ('powershell.exe -NoLogo -NoProfile -Command "$PSVersionTable.PSVersion.ToString()" 2^>^&1') do echo PowerShell: %%V>>"%LOGFILE%"
echo Starting setup script...>>"%LOGFILE%"
echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Setup_GitHub_AutoRelease.ps1" -LogPath "%LOGFILE%" %* 2>>"%LOGFILE%"
set "RC=%ERRORLEVEL%"
>>"%LOGFILE%" echo [%date% %time%] PowerShell exit code: %RC%
if not "%RC%"=="0" goto :failed
echo.
echo Setup process returned successfully.
echo Log file: "%LOGFILE%"
echo If the first GitHub Release is not shown yet, check the Actions tab:
echo https://github.com/goldensw1130/-sw/actions
echo.
pause
echo The console will remain open. Type EXIT and press Enter when you are finished.
exit /b 0
:failed
echo.
echo ================================================================
echo SETUP STOPPED. Exit code: %RC%
echo Log file: "%LOGFILE%"
echo --- Recent diagnostic log ---
if exist "%LOGFILE%" type "%LOGFILE%"
echo --- End diagnostic log ---
echo.
echo The console will remain open. Do not re-run INSTALL repeatedly.
echo If needed, share the log text after removing any personal paths.
pause
echo The console will remain open. Type EXIT and press Enter when you are finished.
exit /b %RC%
