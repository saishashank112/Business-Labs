# AI Tech Consultant - One-Command Startup Script (PowerShell)
# Starts all three connected services and their web interfaces

$ROOT_DIR = $PSScriptRoot
$VENV_PYTHON = Join-Path $ROOT_DIR ".venv\Scripts\python.exe"
$VENV_STREAMLIT = Join-Path $ROOT_DIR ".venv\Scripts\streamlit.exe"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  AI Tech Consultant - Starting 3 Connected Systems" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "1. Task 1 (Knowledge Brain API)    : http://localhost:8001" -ForegroundColor Yellow
Write-Host "2. Task 1 (Knowledge Brain UI)     : http://localhost:8501" -ForegroundColor Yellow
Write-Host "3. Task 2 (Inbox Agent Web App)    : http://localhost:3000" -ForegroundColor Yellow
Write-Host "4. Task 3 (Meeting-to-Scope API)   : http://localhost:8002" -ForegroundColor Yellow
Write-Host "5. Task 3 (Meeting-to-Scope UI)    : http://localhost:8502" -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan

# 1. Start Task 1 FastAPI
Write-Host "[1/5] Launching Task 1 Knowledge Brain API on :8001..." -ForegroundColor Green
$t1_api = Start-Process -FilePath $VENV_PYTHON -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port 8001" -WorkingDirectory "$ROOT_DIR\task1-knowledge-brain" -PassThru

# 2. Start Task 1 Streamlit
Write-Host "[2/5] Launching Task 1 Streamlit Explorer on :8501..." -ForegroundColor Green
$t1_ui = Start-Process -FilePath $VENV_STREAMLIT -ArgumentList "run streamlit_app.py --server.port 8501 --server.headless true" -WorkingDirectory "$ROOT_DIR\task1-knowledge-brain" -PassThru

# 3. Start Task 3 FastAPI
Write-Host "[3/5] Launching Task 3 Meeting-to-Scope API on :8002..." -ForegroundColor Green
$t3_api = Start-Process -FilePath $VENV_PYTHON -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port 8002" -WorkingDirectory "$ROOT_DIR\task3-meeting-to-scope" -PassThru

# 4. Start Task 3 Streamlit
Write-Host "[4/5] Launching Task 3 Streamlit Review UI on :8502..." -ForegroundColor Green
$t3_ui = Start-Process -FilePath $VENV_STREAMLIT -ArgumentList "run streamlit_app.py --server.port 8502 --server.headless true" -WorkingDirectory "$ROOT_DIR\task3-meeting-to-scope" -PassThru

# 5. Start Task 2 Next.js App
Write-Host "[5/5] Launching Task 2 Inbox Agent Next.js on :3000..." -ForegroundColor Green
$t2_web = Start-Process -FilePath "npm.cmd" -ArgumentList "run dev -- -p 3000" -WorkingDirectory "$ROOT_DIR\task2-inbox-agent" -PassThru

Write-Host "`nAll 5 services have been started in the background!" -ForegroundColor Cyan
Write-Host "Press Ctrl+C or close this console to terminate all services." -ForegroundColor White

try {
    while ($true) {
        Start-Sleep -Seconds 2
    }
} finally {
    Write-Host "`nShutting down all AI Tech Consultant services..." -ForegroundColor Magenta
    Stop-Process -Id $t1_api.Id -ErrorAction SilentlyContinue
    Stop-Process -Id $t1_ui.Id -ErrorAction SilentlyContinue
    Stop-Process -Id $t3_api.Id -ErrorAction SilentlyContinue
    Stop-Process -Id $t3_ui.Id -ErrorAction SilentlyContinue
    Stop-Process -Id $t2_web.Id -ErrorAction SilentlyContinue
    Write-Host "Shutdown complete." -ForegroundColor Green
}
