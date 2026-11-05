@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Creating Python virtual environment...
    py -m venv .venv
)
call ".venv\Scripts\activate.bat"
echo Installing or checking required packages...
python -m pip install -r requirements.txt
if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo.
    echo Created backend\.env from the example file.
    echo Open backend\.env and add your Gemini and Tavily API keys, then run this file again.
    pause
    exit /b 0
)
echo Starting AI Lesson Generator API...
python -m uvicorn app.main:app --reload
