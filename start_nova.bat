@echo off
cd /d "%~dp0"

echo =======================================================
echo          Starting NOVA AI Assistant
echo =======================================================

:: Start Ollama in background if not already running
tasklist /fi "imagename eq ollama.exe" 2>NUL | find /i "ollama.exe" >NUL
if "%ERRORLEVEL%"=="1" (
    echo Starting Ollama server with GPU acceleration...
    if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
        start "" /b "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve
    ) else (
        start "" /b ollama serve
    )
    timeout /t 2 /nobreak >nul
)

:: Run NOVA using Anaconda Python or system python
if exist "C:\Users\Admin\anaconda3\python.exe" (
    "C:\Users\Admin\anaconda3\python.exe" main.py
) else (
    python main.py
)
