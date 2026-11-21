$ErrorActionPreference = 'Stop'
$health = Invoke-RestMethod http://127.0.0.1:8000/health -TimeoutSec 10
if ($health.status -ne 'ok') { throw 'Health endpoint did not return ok.' }
$uiResponse = curl.exe --silent --fail http://127.0.0.1:8000/
if ($LASTEXITCODE -ne 0 -or $uiResponse -notmatch 'PaperLens') { throw 'UI smoke check failed.' }
Write-Host 'Health and UI smoke checks passed.'
