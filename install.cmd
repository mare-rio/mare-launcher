@echo off
setlocal
set "PYTHONUTF8=1"
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 install.py %*
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Install Python 3.9 or later from python.org. Then run this command again. Help: docs/INSTALLATION.md.
    pause
    exit /b 1
  )
  python install.py %*
)
set "MARE_INSTALL_RESULT=%errorlevel%"
pause
exit /b %MARE_INSTALL_RESULT%
