$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $scriptDir

if (-not (Test-Path .\venv\Scripts\python.exe)) {
    Write-Host "Creating virtual environment..."
    python -m venv venv
}

. .\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install --only-binary=:all: -r requirements.txt
python -m streamlit run app.py --server.port 8505
