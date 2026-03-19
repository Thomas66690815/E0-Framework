@echo off
REM E0 Network v4 Launcher
REM Starts the orchestrator with Python 3.11
cd /d "%~dp0"

set PYTHON=C:\Users\Thoma\AppData\Local\Programs\Python\Python311\python.exe

echo E0 Network v4 starting...
echo Python: %PYTHON%
echo.

"%PYTHON%" -u e0_init_v3_orchestrator.py %*
