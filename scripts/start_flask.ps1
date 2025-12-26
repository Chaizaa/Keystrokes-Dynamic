# Start Flask Script - No Cache Issues
# Usage: .\start_flask.ps1

Write-Host ""
Write-Host "════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  STARTING FLASK (NO BYTECODE CACHE)" -ForegroundColor Cyan
Write-Host "════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# 1. Kill existing Python processes
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Host "✅ Killed existing Python processes" -ForegroundColor Green

# 2. Delete __pycache__ if exists
if (Test-Path "__pycache__") {
    Remove-Item -Recurse -Force __pycache__
    Write-Host "✅ Deleted __pycache__" -ForegroundColor Green
}

# 3. Set environment variable to disable .pyc generation
$env:PYTHONDONTWRITEBYTECODE = "1"
Write-Host "✅ Bytecode caching DISABLED" -ForegroundColor Green

Write-Host ""
Write-Host "🚀 Starting Flask..." -ForegroundColor Yellow
Write-Host ""

# 4. Activate venv and run Flask
& ..\venv\Scripts\Activate.ps1
python app.py
