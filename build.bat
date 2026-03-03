@echo off
echo ============================================
echo  DataAce - Build Script
echo ============================================

:: Step 1: Build React frontend
echo.
echo [1/3] Building React frontend...
cd frontend
call npm install
call npm run build
if errorlevel 1 (
    echo ERROR: React build failed.
    pause
    exit /b 1
)
cd ..

:: Step 2: Copy React build to FastAPI static folder
echo.
echo [2/3] Copying frontend to src/static...
if exist src\static rmdir /s /q src\static
xcopy /e /i frontend\build src\static
if errorlevel 1 (
    echo ERROR: Failed to copy static files.
    pause
    exit /b 1
)

:: Step 3: Package with PyInstaller
echo.
echo [3/3] Packaging with PyInstaller...
F:\IdeaProject\DataAce\.venv\Scripts\pip.exe install pyinstaller --quiet
F:\IdeaProject\DataAce\.venv\Scripts\pyinstaller.exe DataAce.spec --clean
if errorlevel 1 (
    echo ERROR: PyInstaller packaging failed.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Build complete!
echo  Output: dist\DataAce.exe
echo ============================================
pause
