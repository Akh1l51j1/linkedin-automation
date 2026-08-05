@echo off
echo ========================================
echo   Installing Python dependencies...
echo ========================================
call venv\Scripts\activate.bat
pip install fastapi "uvicorn[standard]" pydantic apscheduler requests feedparser arxiv python-dotenv
echo.
echo ========================================
echo   Installing Frontend dependencies...
echo ========================================
cd frontend
call npm install
cd ..
echo.
echo ========================================
echo   All done! Now run: start.bat
echo ========================================
pause
