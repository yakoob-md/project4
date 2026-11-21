param([string]$GroqApiKey = $env:GROQ_API_KEY)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
foreach ($command in 'python','node','docker') {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) { throw "$command is required and was not found." }
}
function New-Secret([int]$Bytes = 32) {
    $buffer = New-Object byte[] $Bytes
    $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($buffer)
    } finally {
        $generator.Dispose()
    }
    [Convert]::ToBase64String($buffer).Replace('+','-').Replace('/','_').TrimEnd('=')
}
if (-not $GroqApiKey) {
    $secureKey = Read-Host 'Groq API key' -AsSecureString
    $keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
    try {
        $GroqApiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
    }
}
if ([string]::IsNullOrWhiteSpace($GroqApiKey)) { throw 'A Groq API key is required.' }
if (-not (Test-Path .env)) {
    $environmentLines = @(
        'PAPERLENS_ENV=local'
        'AUTH_MODE=dev'
        "GROQ_API_KEY=$GroqApiKey"
        'PAPERLENS_MODEL=openai/gpt-oss-20b'
        "JWT_SECRET=$(New-Secret)"
        "INVITE_CODE=$(New-Secret 18)"
        "SERVICE_TOKEN=$(New-Secret)"
        "POSTGRES_PASSWORD=$(New-Secret)"
    )
    [IO.File]::WriteAllLines((Join-Path (Get-Location) '.env'), $environmentLines, (New-Object Text.UTF8Encoding($false)))
    Write-Host 'Created .env with generated local secrets.'
} else { Write-Host '.env already exists. It was left unchanged.' }
docker info | Out-Null
Write-Host 'Bootstrap checks passed.'
