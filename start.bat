@echo off
title FreshGen Trading Dashboard
cd /d "D:\download\fresh gen"

echo.
echo ============================================
echo   FreshGen - Qullamaggie Trading System
echo ============================================
echo.

echo [1/2] Starting backend (FastAPI)...
start "FreshGen Backend" cmd /k "cd /d D:\download\fresh gen && python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload"

echo Waiting 4 seconds for backend...
timeout /t 4 /nobreak > nul

echo [2/2] Starting frontend (Next.js)...
start "FreshGen Frontend" cmd /k "cd /d D:\download\fresh gen\dashboard && npm run dev"

echo Waiting 6 seconds for frontend...
timeout /t 6 /nobreak > nul

echo Opening dashboard...
start http://localhost:3000

echo.
echo  Dashboard  ^>  http://localhost:3000
echo  Backend    ^>  http://localhost:8000
echo  API Docs   ^>  http://localhost:8000/docs
echo.
echo Close the two terminal windows to stop everything.
echo.
pause
