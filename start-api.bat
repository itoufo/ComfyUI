@echo off
setlocal

echo ============================================
echo  ComfyUI + API Proxy + Cloudflare Tunnel
echo ============================================
echo.

cd /d "%~dp0"

set CLOUDFLARED="%USERPROFILE%\AppData\Local\Microsoft\WinGet\Packages\Cloudflare.cloudflared_Microsoft.Winget.Source_8wekyb3d8bbwe\cloudflared.exe"

REM --- Step 1: ComfyUI ---
echo [1/3] Starting ComfyUI on 127.0.0.1:8188...
start "ComfyUI" cmd /k "call C:\Users\yuhoi\anaconda3\Scripts\activate.bat comfyui && cd /d C:\Users\yuhoi\ComfyUI && python main.py --listen 127.0.0.1 --port 8188"

REM Wait for ComfyUI to initialize
echo      Waiting for ComfyUI to start...
timeout /t 10 /nobreak >nul

REM --- Step 2: API Proxy ---
REM Check if .env exists; if not, it will be auto-generated
if not exist "api_proxy\.env" (
    echo [INFO] First run detected. API key will be auto-generated.
    echo.
)

echo [2/3] Starting API proxy on 127.0.0.1:8189...
start "ComfyUI API Proxy" cmd /k "call C:\Users\yuhoi\anaconda3\Scripts\activate.bat comfyui && cd /d C:\Users\yuhoi\ComfyUI && python -m uvicorn api_proxy.main:app --host 127.0.0.1 --port 8189 --log-level info"

REM Wait for proxy to start
timeout /t 3 /nobreak >nul

REM Show the API key
echo.
echo ============================================
if exist "api_proxy\.env" (
    for /f "tokens=2 delims==" %%a in ('findstr /b "API_KEY=" "api_proxy\.env"') do (
        echo  API Key: %%a
    )
)
echo ============================================
echo.

REM --- Step 3: Cloudflare Tunnel ---
echo [3/3] Cloudflare Tunnel
echo.
echo Options:
echo   1. Start tunnel (comfyui.aifrends.com + tts.aifrends.com)
echo   2. Skip tunnel (local access only)
echo.
set /p TUNNEL_CHOICE="Select option [1/2]: "

if "%TUNNEL_CHOICE%"=="1" (
    echo.
    echo Starting Cloudflare Tunnel...
    start "Cloudflare Tunnel" cmd /k "%CLOUDFLARED% tunnel run"
) else (
    echo Skipping tunnel. Proxy is accessible at http://127.0.0.1:8189
)

echo.
echo ============================================
echo  ComfyUI:          http://127.0.0.1:8188
echo  Proxy running at: http://127.0.0.1:8189
echo  Public URL:       https://comfyui.aifrends.com
echo  Health check:     curl http://127.0.0.1:8189/health
echo ============================================
echo.
echo Press any key to exit this launcher (all services will keep running)...
pause >nul
