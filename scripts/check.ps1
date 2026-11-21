$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Python tests failed.' }
node --check paperlens/web/app.js
if ($LASTEXITCODE -ne 0) { throw 'JavaScript syntax check failed.' }
docker compose config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Compose validation failed.' }
