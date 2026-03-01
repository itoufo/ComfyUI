@echo off
setlocal

echo ============================================
echo  ComfyUI API Proxy - Initial Setup
echo ============================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+.
    pause
    exit /b 1
)

REM Install Python dependencies
echo [1/3] Installing Python dependencies...
pip install fastapi "uvicorn[standard]" httpx websockets pydantic-settings
if errorlevel 1 (
    echo [ERROR] Failed to install Python dependencies.
    pause
    exit /b 1
)
echo      Done.
echo.

REM Check/Install cloudflared
echo [2/3] Checking cloudflared...
cloudflared --version >nul 2>&1
if errorlevel 1 (
    echo      cloudflared not found. Installing via winget...
    winget install --id Cloudflare.cloudflared --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo [WARN] winget install failed. Please install cloudflared manually:
        echo        https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
    ) else (
        echo      cloudflared installed.
    )
) else (
    echo      cloudflared already installed.
)
echo.

REM Generate .env if needed
echo [3/3] Checking .env configuration...
if not exist "%~dp0api_proxy\.env" (
    echo      .env will be auto-generated on first run with a random API key.
) else (
    echo      .env already exists.
)
echo.

echo ============================================
echo  Setup complete!
echo.
echo  Next steps:
echo    1. Start ComfyUI normally (make sure it runs on port 8188)
echo    2. Run start-api.bat to launch the proxy and tunnel
echo    3. Your API key will be shown on first launch
echo ============================================
pause
