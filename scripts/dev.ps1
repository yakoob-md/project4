$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path .env)) { throw 'Run scripts/bootstrap.ps1 first.' }
docker compose up --build --detach --wait
if ($LASTEXITCODE -ne 0) { throw 'Local stack failed to start.' }
Write-Host 'PaperLens is ready at http://127.0.0.1:8000'
