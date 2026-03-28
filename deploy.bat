@echo off
REM Deployment helper script for Gunshot Detector (Windows)

setlocal enabledelayedexpansion

echo.
echo ===================================
echo Gunshot Detector Deployment Helper
echo ===================================
echo.

REM Check if Docker is installed
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker is not installed. Please install Docker Desktop first.
    exit /b 1
)

REM Check if Docker Compose is installed
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker Compose is not installed. Please install Docker Compose first.
    exit /b 1
)

REM Function: Build image
:build_image
echo.
echo 🔨 Building Docker image...
docker-compose build
if errorlevel 1 (
    echo ❌ Build failed!
    exit /b 1
)
echo ✅ Image built successfully!
goto menu

REM Function: Start app
:start_app
echo.
echo 🚀 Starting application...
docker-compose up -d
if errorlevel 1 (
    echo ❌ Failed to start application!
    exit /b 1
)
echo ✅ Application started!
echo.
echo 📍 Dashboard available at: http://localhost:6990
echo.
timeout /t 2 >nul
docker-compose logs
goto menu

REM Function: Stop app
:stop_app
echo.
echo 🛑 Stopping application...
docker-compose down
if errorlevel 1 (
    echo ❌ Failed to stop application!
    exit /b 1
)
echo ✅ Application stopped!
goto menu

REM Function: Restart app
:restart_app
echo.
echo 🔄 Restarting application...
docker-compose restart
if errorlevel 1 (
    echo ❌ Failed to restart application!
    exit /b 1
)
echo ✅ Application restarted!
goto menu

REM Function: Check status
:check_status
echo.
echo 📊 Checking application status...
docker-compose ps
if errorlevel 1 (
    echo ❌ Application is not running!
    goto menu
)
echo.
echo ✅ Application is running!
goto menu

REM Function: Setup env
:setup_env
if exist .env (
    echo ℹ️  .env file already exists.
) else (
    echo 📝 Creating .env file from template...
    copy .env.example .env
    if errorlevel 1 (
        echo ❌ Failed to create .env file!
        goto menu
    )
    echo ✅ .env file created. Please edit it with your email configuration.
    echo 📍 Edit: .env
)
goto menu

REM Function: View logs
:view_logs
echo.
echo 📋 Showing application logs (Press Ctrl+C to exit)...
docker-compose logs -f gunshot-detector
goto menu

REM Function: Clean up
:clean
echo.
echo 🧹 Cleaning up Docker resources...
docker-compose down -v
if errorlevel 1 (
    echo ❌ Cleanup failed!
    goto menu
)
echo ✅ Cleanup completed!
goto menu

REM Function: Full setup
:full_setup
call :setup_env
call :build_image
call :start_app
goto menu

REM Main menu
:menu
cls
echo.
echo ===================================
echo Gunshot Detector Deployment Helper
echo ===================================
echo.
echo What would you like to do?
echo 1^) Setup environment (.env file)
echo 2^) Build Docker image
echo 3^) Start application
echo 4^) Stop application
echo 5^) Restart application
echo 6^) Check status
echo 7^) View logs
echo 8^) Clean up (stop and remove containers)
echo 9^) Full setup (environment + build + start)
echo 0^) Exit
echo.
set /p option="Select an option (0-9): "

if "%option%"=="1" goto setup_env
if "%option%"=="2" goto build_image
if "%option%"=="3" goto start_app
if "%option%"=="4" goto stop_app
if "%option%"=="5" goto restart_app
if "%option%"=="6" goto check_status
if "%option%"=="7" goto view_logs
if "%option%"=="8" goto clean
if "%option%"=="9" goto full_setup
if "%option%"=="0" (
    echo.
    echo 👋 Goodbye!
    exit /b 0
)

echo.
echo ❌ Invalid option. Please try again.
timeout /t 2 >nul
goto menu
