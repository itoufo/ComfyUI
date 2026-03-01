@echo off
setlocal

echo ============================================
echo  ComfyUI API Proxy + Cloudflare Tunnel
echo ============================================
echo.

cd /d "%~dp0"

REM Check if .env exists; if not, it will be auto-generated
if not exist "api_proxy\.env" (
    echo [INFO] First run detected. API key will be auto-generated.
    echo.
)

REM Start the API proxy
echo [1/2] Starting API proxy on 127.0.0.1:8189...
start "ComfyUI API Proxy" cmd /k "cd /d %~dp0 && python -m uvicorn api_proxy.main:app --host 127.0.0.1 --port 8189 --log-level info"

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

REM Ask about Cloudflare Tunnel
echo [2/2] Cloudflare Tunnel
echo.
echo Options:
echo   1. Start quick tunnel (temporary URL, no config needed)
echo   2. Start named tunnel (requires 'cloudflared tunnel login' first)
echo   3. Skip tunnel (local access only)
echo.
set /p TUNNEL_CHOICE="Select option [1/2/3]: "

if "%TUNNEL_CHOICE%"=="1" (
    echo.
    echo Starting quick tunnel...
    start "Cloudflare Tunnel" cmd /k "cloudflared tunnel --url http://127.0.0.1:8189"
) else if "%TUNNEL_CHOICE%"=="2" (
    set /p TUNNEL_NAME="Enter tunnel name: "
    echo.
    echo Starting named tunnel...
    start "Cloudflare Tunnel" cmd /k "cloudflared tunnel run --url http://127.0.0.1:8189 %TUNNEL_NAME%"
) else (
    echo Skipping tunnel. Proxy is accessible at http://127.0.0.1:8189
)

echo.
echo ============================================
echo  Proxy running at: http://127.0.0.1:8189
echo  Health check:     curl http://127.0.0.1:8189/health
echo ============================================
echo.
echo Press any key to exit this launcher (proxy and tunnel will keep running)...
pause >nul
