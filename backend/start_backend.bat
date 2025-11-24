@echo off
echo ========================================
echo   Company Research Assistant - Backend
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if .env file exists
if not exist ".env" (
    echo.
    echo WARNING: .env file not found!
    echo Please create .env file with:
    echo   LLM_PROVIDER=gemini
    echo   GEMINI_API_KEY=your-api-key
    echo.
    pause
)

REM Check if dependencies are installed
echo Checking dependencies...
python -c "import fastapi" 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
)

REM Create necessary directories
if not exist "vector_db" mkdir vector_db
if not exist "uploads" mkdir uploads

echo.
echo Starting backend server...
echo Backend will be available at: http://localhost:8000
echo API docs will be available at: http://localhost:8000/docs
echo.
echo Press CTRL+C to stop the server
echo.

uvicorn main:app --reload --port 8000

pause

