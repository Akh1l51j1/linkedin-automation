@echo off
echo ========================================
echo   LinkedIn Automation - Starting...
echo ========================================
echo.

:: Start the Python backend (FastAPI on port 8000)
echo [1/2] Starting Backend (FastAPI on port 8000)...
cd /d "%~dp0"
start "LinkedIn Backend" cmd /k "call venv\Scripts\activate.bat && python -m uvicorn api:app --reload --port 8000"

:: Small delay so backend starts first
timeout /t 3 /nobreak > nul

:: Start the frontend (Vite on port 5173)
echo [2/2] Starting Frontend (Vite on port 5173)...
start "LinkedIn Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo ========================================
echo   Both servers are running!
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:5173
echo ========================================
echo.
echo   Close both terminal windows to stop.
echo.
pause
