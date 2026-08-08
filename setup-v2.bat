@echo off
setlocal enabledelayedexpansion
title Migration Intelligence Platform — Setup
color 0B
cls

echo.
echo.
echo  ╔════════════════════════════════════════════════════════╗
echo  ║    Migration Intelligence Platform Installer 2.0       ║
echo  ║    Full-Stack Setup with Dependency Management         ║
echo  ╚════════════════════════════════════════════════════════╝
echo.

REM Check Python installation
echo [CHECKING PREREQUISITES...]
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ✗ ERROR: Python is not installed or not in PATH
    echo  └─ Please install Python 3.9+ from https://www.python.org/
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo  ✓ %PYTHON_VERSION% detected

node --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ✗ ERROR: Node.js is not installed or not in PATH
    echo  └─ Please install Node.js 16+ from https://nodejs.org/
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('node --version') do set NODE_VERSION=%%i
echo  ✓ Node.js !NODE_VERSION! detected

npm --version >nul 2>&1
if errorlevel 1 (
    echo  ✗ ERROR: npm is not installed
    echo  └─ Reinstall Node.js with npm included
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('npm --version') do set NPM_VERSION=%%i
echo  ✓ npm !NPM_VERSION! detected

echo.
echo  ✓ All prerequisites verified
echo.
pause

REM Create virtual environment if it doesn't exist
if not exist ".venv" (
    echo [STEP 1/4] Creating Python virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo  ✗ Failed to create virtual environment
        pause
        exit /b 1
    )
    echo  ✓ Virtual environment created
) else (
    echo [STEP 1/4] Virtual environment already exists
)

echo.
echo [STEP 2/4] Activating virtual environment...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo  ✗ Failed to activate virtual environment
    pause
    exit /b 1
)
echo  ✓ Virtual environment activated

echo.
echo [STEP 3/4] Installing frontend dependencies...
cd frontend
call npm install --legacy-peer-deps
if errorlevel 1 (
    echo.
    echo  ✗ Frontend installation failed
    cd ..
    pause
    exit /b 1
)
echo  ✓ Frontend dependencies installed
cd ..

echo.
echo [STEP 4/4] Installing backend dependencies...
cd backend
python -m pip install --upgrade pip
if errorlevel 1 (
    echo  ⚠ Warning: pip upgrade had issues (continuing anyway)
)

python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo  ✗ Backend dependencies installation failed
    echo  └─ Check requirements.txt for compatibility issues
    cd ..
    pause
    exit /b 1
)
echo  ✓ Backend dependencies installed
cd ..

echo.
echo [SETUP] Configuring environment...
call npm run setup
if errorlevel 1 (
    echo  ⚠ Warning: Environment setup encountered issues
)
echo  ✓ Environment configuration complete

echo.
echo.
echo  ╔════════════════════════════════════════════════════════╗
echo  ║              ✓ Installation Complete!                  ║
echo  ╚════════════════════════════════════════════════════════╝
echo.
echo  📋 NEXT STEPS — Running the application:
echo.
echo  Option 1: Development Mode (with auto-reload)
echo  ─────────────────────────────────────────────────────
echo   Terminal 1 (Frontend):
echo     cd frontend
echo     npm run dev
echo     → Open http://localhost:3000
echo.
echo   Terminal 2 (Backend):
echo     cd backend
echo     python -m uvicorn main:app --reload
echo     → API Docs: http://localhost:8000/docs
echo.
echo  Option 2: Production Build
echo  ─────────────────────────────────────────────────────
echo   # Frontend production
echo   cd frontend
echo   npm run build
echo   npm start
echo.
echo   # Backend production
echo   cd backend
echo   pip install -r ../requirements-prod.txt
echo   gunicorn -w 4 main:app
echo.
echo  📖 For detailed setup instructions, see INSTALLATION_GUIDE.md
echo.
echo  ⚙️  Environment Configuration
echo  ─────────────────────────────────────────────────────
echo   - .env file has been created/updated
echo   - Add your GEMINI_API_KEY to .env if needed
echo.
echo  🔧 Troubleshooting
echo  ─────────────────────────────────────────────────────
echo   If you encounter issues:
echo   1. Check INSTALLATION_GUIDE.md for detailed help
echo   2. Ensure Python 3.9+ and Node.js 16+ are installed
echo   3. Try: .venv\Scripts\deactivate
echo      Then: .venv\Scripts\activate
echo      Then: cd backend && pip install -r requirements.txt
echo.
echo  ╔════════════════════════════════════════════════════════╗
echo  ║            Happy Coding! 🚀                            ║
echo  ╚════════════════════════════════════════════════════════╝
echo.
pause
