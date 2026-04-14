# setup_env.ps1
# Full environment setup for CVEmbed AI (Production Upgrade)
# Run this script from the project root directory.

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "  CVEmbed AI - Environment Setup Script" -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Remove old venv if it exists
if (Test-Path -Path "venv") {
    Write-Host "[1/4] Removing existing 'venv' directory..." -ForegroundColor Yellow
    Remove-Item -Path "venv" -Recurse -Force
    Write-Host "      Done." -ForegroundColor Green
} else {
    Write-Host "[1/4] No existing venv found — skipping removal." -ForegroundColor DarkGray
}

# 2. Create fresh venv
Write-Host ""
Write-Host "[2/4] Creating new virtual environment..." -ForegroundColor Cyan
python -m venv venv
if (-not (Test-Path -Path "venv\Scripts\python.exe")) {
    Write-Host "ERROR: Virtual environment creation failed." -ForegroundColor Red
    Write-Host "Make sure Python is installed and accessible from your PATH." -ForegroundColor Red
    exit 1
}
Write-Host "      Virtual environment created successfully." -ForegroundColor Green

# 3. Upgrade pip
Write-Host ""
Write-Host "[3/4] Upgrading pip..." -ForegroundColor Cyan
.\venv\Scripts\python.exe -m pip install --upgrade pip --quiet
Write-Host "      pip upgraded." -ForegroundColor Green

# 4. Install dependencies
Write-Host ""
Write-Host "[4/4] Installing project dependencies..." -ForegroundColor Cyan
Write-Host "      NOTE: This includes torch, transformers, sentence-transformers." -ForegroundColor DarkCyan
Write-Host "      Please wait — this may take 5-15 minutes. Do NOT press Ctrl+C." -ForegroundColor DarkYellow
Write-Host ""

.\venv\Scripts\pip.exe install -r requirements.txt

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Some dependencies failed to install." -ForegroundColor Red
    Write-Host "Check the error output above." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Green
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "=====================================================" -ForegroundColor Green
Write-Host ""
Write-Host "To run the application:" -ForegroundColor Cyan
Write-Host "  .\venv\Scripts\python.exe app.py" -ForegroundColor White
Write-Host ""
Write-Host "The app will be available at: http://localhost:5000" -ForegroundColor Cyan
Write-Host ""
