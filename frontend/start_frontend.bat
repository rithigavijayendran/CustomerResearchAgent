@echo off
echo ========================================
echo   Company Research Assistant - Frontend
echo ========================================
echo.

REM Check if node_modules exists
if not exist "node_modules\" (
    echo Installing dependencies...
    call npm install
)

REM Check if .env.local exists
if not exist ".env.local" (
    echo.
    echo Creating .env.local file...
    echo NEXT_PUBLIC_API_URL=http://localhost:8000 > .env.local
    echo .env.local file created!
)

echo.
echo Starting frontend development server...
echo Frontend will be available at: http://localhost:3000
echo.
echo Press CTRL+C to stop the server
echo.

npm run dev

pause

