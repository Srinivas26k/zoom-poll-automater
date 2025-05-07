@echo off
setlocal EnableDelayedExpansion

:: Set title and clear screen
title Zoom Poll Automator
cls

:: Print header with colors
echo [92m================================================[0m
echo [92m           Welcome to Zoom Poll Automator        [0m
echo [92m================================================[0m
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [91m[ERROR] Python is not installed! Please install Python 3.8 or higher.[0m
    echo Download from: https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation!
    pause
    exit /b 1
)

:: Check if Ollama is running
echo [93mChecking Ollama status...[0m
curl -s http://localhost:11434/api/tags >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [91m[ERROR] Ollama is not running or not installed![0m
    echo.
    echo Please follow these steps:
    echo 1. Download Ollama from: https://ollama.ai/
    echo 2. Install Ollama
    echo 3. Open a new terminal and run: ollama serve
    echo 4. Wait for Ollama to start
    echo 5. Run this script again
    echo.
    pause
    exit /b 1
)

:: Create and activate virtual environment if needed
if not exist "venv" (
    echo [93mCreating virtual environment...[0m
    python -m venv venv
    if !ERRORLEVEL! NEQ 0 (
        echo [91m[ERROR] Failed to create virtual environment![0m
        pause
        exit /b 1
    )
    echo [92m✓ Virtual environment created[0m
)

:: Activate virtual environment
call venv\Scripts\activate
if %ERRORLEVEL% NEQ 0 (
    echo [91m[ERROR] Failed to activate virtual environment![0m
    pause
    exit /b 1
)

:: Check dependencies and install if needed
echo [93mChecking dependencies...[0m
python -c "import rich" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [93mInstalling required packages...[0m
    pip install -r requirements.txt
    if %ERRORLEVEL% NEQ 0 (
        echo [91m[ERROR] Failed to install dependencies![0m
        pause
        exit /b 1
    )
    echo [92m✓ Dependencies installed[0m
)

:: Check required models and components
echo [93mChecking required components...[0m
python zoompoller.py check
if %ERRORLEVEL% NEQ 0 (
    echo [91m[ERROR] Component check failed! Please fix the issues above.[0m
    pause
    exit /b 1
)

:: Run setup if no .env exists
if not exist ".env" (
    echo [93mFirst time setup needed...[0m
    python zoompoller.py setup
    if !ERRORLEVEL! NEQ 0 (
        echo [91m[ERROR] Setup failed![0m
        pause
        exit /b 1
    )
)

:: Start the automation
echo.
echo [92mStarting Zoom Poll Automator...[0m
python zoompoller.py run

pause