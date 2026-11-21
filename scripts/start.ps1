param([switch]$Stop)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Install and start Docker Desktop with Linux containers, then run this script again.'
}
if ($Stop) {
    docker compose down
    exit $LASTEXITCODE
}
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host 'Created .env. Set GROQ_API_KEY and PAPERLENS_MODEL there to enable model reviews.'
}
docker compose up --build --detach --wait
if ($LASTEXITCODE -ne 0) { throw 'Container startup failed. Inspect docker compose logs.' }
Write-Host 'PaperLens is available at http://localhost:8000'
