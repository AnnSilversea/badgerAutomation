@echo off
REM Start Badger Automation Web UI (Windows)

echo 🦡 Starting Badger Automation...
echo.

REM Check if .env exists
if not exist .env (
    echo ⚠️  Warning: .env file not found!
    echo Please create a .env file with:
    echo   AZURE_DI_ENDPOINT=your_endpoint
    echo   AZURE_DI_KEY=your_key
    echo.
)

REM Check if virtual environment exists
if exist venv\Scripts\activate.bat (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

REM Start the application
echo Starting FastAPI server...
echo Access the Web UI at: http://localhost:8000
echo.
python app.py

pause

