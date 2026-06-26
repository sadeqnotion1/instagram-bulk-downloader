@echo off
REM Launch instagram-bulk-downloader - keeps the repo root clean.
REM   run.bat <username> --login-user you [--limit N]
chcp 65001 >nul
cd /d "%~dp0"

if "%PYTHON%"=="" set "PYTHON=python"

rem Strip surrounding quotes from PYTHON variable for the where check
set "TEMP_PYTHON=%PYTHON:"=%"
where "%TEMP_PYTHON%" >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python was not found (checked: %PYTHON%^).
    echo Please install Python and ensure it is added to your system PATH.
    echo.
    set EXIT_CODE=1
    goto :pause_exit
)

"%PYTHON%" -m app.main --full %*
set EXIT_CODE=%errorlevel%

:pause_exit
echo %cmdcmdline% | findstr /i /c:" /c " >nul
if %errorlevel%==0 (
    echo.
    echo Press any key to exit . . .
    pause >nul
)
exit /b %EXIT_CODE%
