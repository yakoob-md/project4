$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
& "$PSScriptRoot/check.ps1"
if ($LASTEXITCODE -ne 0) { throw 'Quality checks failed.' }
python -m evaluation.benchmark
if ($LASTEXITCODE -ne 0) { throw 'Seeded deterministic benchmark failed.' }
