<#
.SYNOPSIS
Sets up the Python virtual environment for KhabriChacha on Windows.
#>

$ErrorActionPreference = "Stop"

Write-Host "Setting up KhabriChacha Environment..." -ForegroundColor Cyan

# 1. Check for Python
if (-not (Get-Command "python" -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Python is not installed or not in PATH." -ForegroundColor Red
    exit 1
}

# 2. Create Virtual Environment
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment (.venv)..." -ForegroundColor Yellow
    python -m venv .venv
} else {
    Write-Host "Virtual environment already exists." -ForegroundColor Green
}

# 3. Activate Virtual Environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
$ActivateScript = ".\.venv\Scripts\Activate.ps1"
if (Test-Path $ActivateScript) {
    . $ActivateScript
} else {
    Write-Host "ERROR: Could not find activation script at $ActivateScript" -ForegroundColor Red
    exit 1
}

# 4. Upgrade pip
Write-Host "Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

# 5. Install Requirements
Write-Host "Installing dependencies from requirements.txt..." -ForegroundColor Yellow
pip install -r requirements.txt

# 6. Verify Installation
Write-Host "Verifying installation..." -ForegroundColor Yellow
if (Test-Path "verify_environment.py") {
    python verify_environment.py
} else {
    Write-Host "verify_environment.py not found. Skipping verification." -ForegroundColor Yellow
}

Write-Host "`nEnvironment setup complete! Run the app with: python app.py" -ForegroundColor Green
