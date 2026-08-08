@echo off
REM Installation Validation Script
REM Checks if all dependencies are properly installed

setlocal enabledelayedexpansion
title Installation Validator — Migration Intelligence Platform
color 0B
cls

echo.
echo  ╔════════════════════════════════════════════════════════╗
echo  ║      Installation Validator v2.0                       ║
echo  ║      Checking all dependencies...                      ║
echo  ╚════════════════════════════════════════════════════════╝
echo.

set "RED=[91m"
set "GREEN=[92m"
set "YELLOW=[93m"
set "RESET=[0m"

REM Check Python
echo [CHECK 1/6] Python Installation
python --version >nul 2>&1
if errorlevel 1 (
    echo  ✗ Python NOT installed
    echo      └─ Required: Python 3.9+
    echo      └─ Install from: https://www.python.org/
) else (
    for /f "tokens=*" %%i in ('python --version') do (
        echo  ✓ %%i
    )
)
echo.

REM Check Node.js
echo [CHECK 2/6] Node.js Installation
node --version >nul 2>&1
if errorlevel 1 (
    echo  ✗ Node.js NOT installed
    echo      └─ Required: Node 16+
    echo      └─ Install from: https://nodejs.org/
) else (
    for /f "tokens=*" %%i in ('node --version') do (
        echo  ✓ Node %%i
    )
)
echo.

REM Check npm
echo [CHECK 3/6] npm Installation
npm --version >nul 2>&1
if errorlevel 1 (
    echo  ✗ npm NOT installed
) else (
    for /f "tokens=*" %%i in ('npm --version') do (
        echo  ✓ npm %%i
    )
)
echo.

REM Check Virtual Environment
echo [CHECK 4/6] Python Virtual Environment
if exist ".venv" (
    echo  ✓ Virtual environment found (.venv/)
) else (
    echo  ⚠ Virtual environment NOT found
    echo      └─ Run: python -m venv .venv
)
echo.

REM Check Core Python Packages
echo [CHECK 5/6] Backend Dependencies
if exist ".venv" (
    call .venv\Scripts\activate.bat >nul 2>&1
    
    python -c "import fastapi" >nul 2>&1
    if errorlevel 1 (
        echo  ✗ FastAPI NOT installed
    ) else (
        echo  ✓ FastAPI installed
    )
    
    python -c "import pydantic" >nul 2>&1
    if errorlevel 1 (
        echo  ✗ Pydantic NOT installed
    ) else (
        echo  ✓ Pydantic installed
    )
    
    python -c "import sqlalchemy" >nul 2>&1
    if errorlevel 1 (
        echo  ✗ SQLAlchemy NOT installed
    ) else (
        echo  ✓ SQLAlchemy installed
    )
    
    python -c "import chromadb" >nul 2>&1
    if errorlevel 1 (
        echo  ✗ ChromaDB NOT installed (RAG)
    ) else (
        echo  ✓ ChromaDB installed
    )
    
    python -c "import sklearn" >nul 2>&1
    if errorlevel 1 (
        echo  ✗ scikit-learn NOT installed
    ) else (
        echo  ✓ scikit-learn installed
    )
    
    python -c "import xgboost" >nul 2>&1
    if errorlevel 1 (
        echo  ✗ XGBoost NOT installed
    ) else (
        echo  ✓ XGBoost installed
    )
    
    python -c "import google.genai" >nul 2>&1
    if errorlevel 1 (
        echo  ✗ google-genai NOT installed (LLM)
    ) else (
        echo  ✓ google-genai installed
    )
    
    call .venv\Scripts\deactivate.bat >nul 2>&1
) else (
    echo  ✗ Virtual environment required first
    echo      └─ Run: python -m venv .venv
)
echo.

REM Check Frontend Dependencies
echo [CHECK 6/6] Frontend Dependencies
cd frontend >nul 2>&1
if exist "node_modules" (
    if exist "package.json" (
        echo  ✓ Node modules installed
        
        for /f "tokens=*" %%i in ('npm list next 2^>nul ^| find "next@"') do (
            echo  ✓ Next.js found
        )
    ) else (
        echo  ⚠ package.json not found
    )
) else (
    echo  ⚠ Node modules NOT installed
    echo      └─ Run: npm install
)
cd .. >nul 2>&1
echo.

REM Configuration Check
echo [EXTRA] Configuration Files
if exist ".env" (
    echo  ✓ .env file exists
) else (
    echo  ⚠ .env file NOT found
    echo      └─ Run: npm run setup
)

if exist "requirements.txt" (
    echo  ✓ Requirements.txt exists
) else (
    echo  ✗ requirements.txt NOT found
)

if exist "frontend\package.json" (
    echo  ✓ Frontend package.json exists
) else (
    echo  ✗ Frontend package.json NOT found
)

if exist "backend\main.py" (
    echo  ✓ Backend main.py exists
) else (
    echo  ✗ Backend main.py NOT found
)

echo.
echo.
echo  ╔════════════════════════════════════════════════════════╗
echo  ║           Validation Complete!                         ║
echo  ╚════════════════════════════════════════════════════════╝
echo.
echo  📋 Next Steps:
echo  ─────────────────────────────────────────────────────
echo.
echo  Terminal 1 (Frontend):
echo    cd frontend
echo    npm run dev
echo.
echo  Terminal 2 (Backend):
echo    cd backend
echo    python -m uvicorn main:app --reload
echo.
echo  ✓ Installation is ready!
echo.
pause
