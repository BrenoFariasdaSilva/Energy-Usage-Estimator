@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -3 scripts\launcher.py run
) else (
  python scripts\launcher.py run
)
if ERRORLEVEL 1 (
  echo.
  echo Nao foi possivel iniciar. Instale Python 3.11+ e marque Add Python to PATH.
  pause
)
