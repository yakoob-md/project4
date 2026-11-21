$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
docker compose exec web python -c "from paperlens.storage import connection; connection().__enter__(); print('database ready')"
if ($LASTEXITCODE -ne 0) { throw 'Database initialization failed.' }
docker compose run --no-deps --rm review-worker python -m services.m1_storage
if ($LASTEXITCODE -ne 0) { throw 'M1 evidence migration failed.' }
