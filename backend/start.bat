@echo off
title Interlace Backend
color 0A

echo.
echo  ==========================================
echo   Interlace Backend — FastAPI
echo   http://localhost:8000
echo   http://localhost:8000/docs
echo  ==========================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python tidak ditemukan. Install Python 3.12 dulu.
    pause & exit /b 1
)

:: Install dependencies kalau belum
if not exist ".venv" (
    echo [1/3] Membuat virtual environment...
    python -m venv .venv
    echo [OK]
)

echo [2/3] Aktivasi virtual environment...
call .venv\Scripts\activate.bat

echo [3/3] Install dependencies...
pip install -r requirements.txt -q
echo [OK]

:: Buat folder yang dibutuhkan
if not exist "..\data\processed" mkdir "..\data\processed"
if not exist "..\data\raw\eoi"   mkdir "..\data\raw\eoi"
if not exist "..\ml\serialized"  mkdir "..\ml\serialized"

echo.
echo  Memulai FastAPI server...
echo  Docs: http://localhost:8000/docs
echo  Health: http://localhost:8000/health
echo.

uvicorn main:app --reload --host 0.0.0.0 --port 8000

pause
