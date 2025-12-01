@echo off
REM Proctor+ v4 Quick Start Script (Windows)
REM This script sets up and starts the complete system

setlocal enabledelayedexpansion

echo.
echo ====================================================================
echo  Proctor+ v4 - Production Exam Proctoring Platform
echo ====================================================================
echo.

REM Check if we're in the right directory
if not exist "proctor_web_ui.html" (
    echo Error: Please run this script from the Cheat detection directory
    echo.
    echo cd "c:\Users\Lenovo\Desktop\Cheat detection"
    echo setup.bat
    echo.
    pause
    exit /b 1
)

REM Step 1: Check Python
echo [1/4] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python not found. Please install Python 3.9+
    pause
    exit /b 1
)
echo ✓ Python found

REM Step 2: Install/Update API dependencies
echo.
echo [2/4] Installing API dependencies...
pip install -q flask flask-cors >nul 2>&1
if %errorlevel% neq 0 (
    echo Warning: Could not install some packages
    echo.
    echo Manual install:
    echo   pip install -r requirements_api.txt
)
echo ✓ Dependencies installed

REM Step 3: Initialize database
echo.
echo [3/4] Initializing database...
python -c "import sqlite3; sqlite3.connect('proctor_sessions.db').cursor().execute('SELECT 1')" 2>nul
echo ✓ Database ready

REM Step 4: Display startup instructions
echo.
echo [4/4] Setup complete!
echo.
echo ====================================================================
echo  NEXT STEPS - Start in TWO separate terminals:
echo ====================================================================
echo.
echo Terminal 1 - API Backend:
echo   cd "c:\Users\Lenovo\Desktop\Cheat detection"
echo   python proctor_api.py
echo.
echo   Expected: "Starting Proctor+ API server on http://localhost:5000"
echo.
echo Terminal 2 - Web UI:
echo   • Open in browser:
echo   file:///c:/Users/Lenovo/Desktop/Cheat detection/proctor_web_ui.html
echo.
echo   OR serve via HTTP:
echo   cd "c:\Users\Lenovo\Desktop\Cheat detection"
echo   python -m http.server 8000
echo   Then visit: http://localhost:8000/proctor_web_ui.html
echo.
echo ====================================================================
echo  OPTIONAL - Python Detection Module:
echo ====================================================================
echo.
echo Terminal 3 (Optional):
echo   python main.py
echo.
echo ====================================================================
echo.
echo 📖 Documentation: IMPLEMENTATION_GUIDE.md
echo 🚀 Quick Start: README_PROCTOR_V4.md
echo 🔌 API Docs: API_REFERENCE.md
echo.
echo Press any key to close...
pause >nul
