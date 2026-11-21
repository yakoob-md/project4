param([switch]$Offline, [switch]$VerifyLangfuse)

$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

function Invoke-Compose {
    docker compose @args | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose command failed ($LASTEXITCODE)" }
}

Invoke-Compose build mcp-tools literature-adk review-worker
Invoke-Compose run --no-deps --rm review-worker python -m unittest services.review_worker.test_artifact -v
if ($Offline) { return }
if ($VerifyLangfuse -and (
    !$env:LANGFUSE_HOST -or !$env:LANGFUSE_PUBLIC_KEY -or !$env:LANGFUSE_SECRET_KEY -or !$env:LANGFUSE_PROJECT_ID
)) { throw 'Set LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY and LANGFUSE_PROJECT_ID in the shell.' }

Invoke-Compose up --detach --wait --wait-timeout 120 postgres jaeger mcp-tools literature-adk review-worker
Invoke-Compose exec -T postgres psql -U paperlens -d paperlens -v ON_ERROR_STOP=1 -c 'CREATE EXTENSION IF NOT EXISTS vector;'
$runId = [guid]::NewGuid().ToString()
Write-Host "M0 live run $runId"
try {
    $result = Invoke-RestMethod -Method Post -TimeoutSec 120 -Uri "http://127.0.0.1:8002/interop?run_id=$runId"
} catch {
    if ($_.ErrorDetails.Message) { Write-Host $_.ErrorDetails.Message }
    throw 'Live worker request failed.'
}
if (
    $result.run_id -ne $runId -or $result.trace_id -notmatch '^[0-9a-f]{32}$' -or
    $result.pdf.tool -ne 'parse_pdf' -or $result.pdf.passages -lt 1 -or !$result.pdf.mcp_protocol -or
    $result.a2a.card -ne 'paperlens_literature' -or $result.a2a.state -ne 'completed' -or !$result.a2a.task_id -or
    $result.a2a.binding -ne 'JSONRPC' -or $result.a2a.protocol_version -ne '1.0' -or
    $result.a2a.media_type -ne 'application/vnd.paperlens.evidence-bundle+json' -or
    !$result.a2a.bundle_id -or $result.a2a.bundle_id -ne $result.crewai.consumed_bundle_id -or
    $result.literature.tool -ne 'search_literature' -or $result.literature.provider -ne 'arXiv' -or
    $result.literature.records -lt 1 -or !$result.literature.mcp_protocol -or
    $result.crewai.tasks -ne 1 -or $result.crewai.usage.total_tokens -lt 1
) { throw 'Live worker results did not meet the M0 assertions.' }

$traceUrl = "http://127.0.0.1:16686/trace/$($result.trace_id)"
$spanParents = @{
    'worker.mcp.parse_pdf' = 'worker.m0'
    'mcp.parse_pdf' = 'worker.mcp.parse_pdf'
    'worker.a2a.discover' = 'worker.m0'
    'worker.a2a.send' = 'worker.m0'
    'adk.a2a.execute' = 'worker.a2a.send'
    'adk.retrieve' = 'adk.a2a.execute'
    'adk.mcp.search_literature' = 'adk.retrieve'
    'mcp.search_literature' = 'adk.mcp.search_literature'
    'worker.crewai.confirm' = 'worker.m0'
}
$verified = $false
for ($attempt = 0; $attempt -lt 20; $attempt++) {
    try {
        $trace = Invoke-RestMethod -TimeoutSec 3 -Uri "http://127.0.0.1:16686/api/traces/$($result.trace_id)"
    } catch {
        Start-Sleep -Seconds 1
        continue
    }
    $spans = @{}
    foreach ($span in $trace.data.spans) {
        if ($span.tags | Where-Object { $_.key -eq 'paperlens.run_id' -and $_.value -eq $runId }) {
            $spans[$span.operationName] = $span
        }
    }
    $verified = $true
    foreach ($name in $spanParents.Keys) {
        $parent = $spans[$spanParents[$name]]
        if (!$parent -or !$spans[$name] -or $parent.spanID -notin $spans[$name].references.spanID) {
            $verified = $false
            break
        }
    }
    if ($verified) { break }
    Start-Sleep -Seconds 1
}
if (!$verified) { throw "Missing correlated trace spans or parent links at $traceUrl" }
$result | Add-Member -NotePropertyName jaeger_trace_url -NotePropertyValue $traceUrl
$result | Add-Member -NotePropertyName malformed_artifact -NotePropertyValue 'rejected (offline A2A protobuf fixture)'
if ($VerifyLangfuse) {
    $hostUrl = $env:LANGFUSE_HOST.TrimEnd('/')
    $credentials = "${env:LANGFUSE_PUBLIC_KEY}:${env:LANGFUSE_SECRET_KEY}"
    $auth = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($credentials))
    $observationsUrl = "$hostUrl/api/public/v2/observations?traceId=$($result.trace_id)&fields=core,basic"
    $verified = $false
    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        $remote = Invoke-RestMethod -TimeoutSec 8 -Uri $observationsUrl -Headers @{Authorization = "Basic $auth"}
        $observations = @{}
        foreach ($observation in $remote.data) { $observations[$observation.name] = $observation }
        $verified = $true
        foreach ($name in $spanParents.Keys) {
            $parent = $observations[$spanParents[$name]]
            if (!$parent -or !$observations[$name] -or $observations[$name].parentObservationId -ne $parent.id) {
                $verified = $false
                break
            }
        }
        if ($verified) { break }
        Start-Sleep -Seconds 3
    }
    if (!$verified) { throw "Langfuse did not return the correlated M0 spans for trace $($result.trace_id)." }
    $result | Add-Member -NotePropertyName langfuse_trace_url -NotePropertyValue (
        "$hostUrl/project/$env:LANGFUSE_PROJECT_ID/traces/$($result.trace_id)"
    )
}
$result | ConvertTo-Json -Depth 8
