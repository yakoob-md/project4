param([switch]$Live)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

docker compose run --no-deps --rm review-worker python -m services.m1_storage
if ($LASTEXITCODE -ne 0) { throw 'M1 migration failed.' }

if (-not $Live) {
    docker compose run --no-deps --rm mcp-tools python -m unittest services.mcp_tools.test_literature -v
    if ($LASTEXITCODE -ne 0) { throw 'MCP provider fixture checks failed.' }
    docker compose run --no-deps --rm review-worker python -m unittest services.review_worker.test_artifact services.review_worker.test_ingestion -v
    if ($LASTEXITCODE -ne 0) { throw 'M1 fixture checks failed.' }
    exit
}

$written = docker compose run --no-deps --rm review-worker python -m services.review_worker.smoke_ingestion
if ($LASTEXITCODE -ne 0) { throw 'Live M1 ingestion failed.' }
$expected = $written | ConvertFrom-Json
$reloaded = docker compose run --no-deps --rm review-worker python -m services.review_worker.smoke_ingestion --read $expected.bundle_id
if ($LASTEXITCODE -ne 0) { throw 'Reload in a new process failed.' }
$actual = $reloaded | ConvertFrom-Json
if ($actual.bundle_id -ne $expected.bundle_id -or $actual.sha256 -ne $expected.sha256) {
    throw 'Frozen bundle changed across processes.'
}
$reloaded

