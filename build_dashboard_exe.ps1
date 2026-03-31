$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (-not (Test-Path -LiteralPath ".venv")) {
  python -m venv .venv
}

& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install pyinstaller

& ".\.venv\Scripts\pyinstaller.exe" `
  --noconfirm `
  --clean `
  --name "KnowledgeEngineDashboard" `
  --onefile `
  --windowed `
  --add-data "web;web" `
  dashboard.py

Write-Host ""
Write-Host "Build done: dist\\KnowledgeEngineDashboard.exe"
