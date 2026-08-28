param(
    [Parameter(Mandatory = $true)]
    [string]$PythonPath,
    [Parameter(Mandatory = $true)]
    [string]$DataDirectory,
    [int]$Port = 18081
)

$ErrorActionPreference = "Stop"
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$dataRoot = [System.IO.Path]::GetFullPath($DataDirectory)
if (Test-Path -LiteralPath $dataRoot) {
    throw "Smoke-test data directory already exists: $dataRoot"
}
New-Item -ItemType Directory -Path $dataRoot | Out-Null

$logRoot = Split-Path -Parent $dataRoot
$stdout1 = Join-Path $logRoot "runtime-1.stdout.log"
$stderr1 = Join-Path $logRoot "runtime-1.stderr.log"
$stdout2 = Join-Path $logRoot "runtime-2.stdout.log"
$stderr2 = Join-Path $logRoot "runtime-2.stderr.log"
$baseUrl = "http://127.0.0.1:$Port"

$env:DATA_DIR = $dataRoot
$env:SECRET_KEY = ""
$env:PUBLIC_BASE_URL = ""
$env:HOST = "127.0.0.1"
$env:PORT = "$Port"
$env:FORWARDED_ALLOW_IPS = "127.0.0.1"
$env:PYTHONUNBUFFERED = "1"

function Wait-ForHealth {
    for ($attempt = 1; $attempt -le 60; $attempt++) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing "$baseUrl/health" -TimeoutSec 2
            if ($response.StatusCode -eq 200) {
                return
            }
        } catch {
            # Startup may still be in progress.
        }
        Start-Sleep -Milliseconds 500
    }
    throw "Local runtime did not become healthy"
}

function Stop-SmokeProcess([System.Diagnostics.Process]$Process) {
    if ($Process -and -not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force
        Wait-Process -Id $Process.Id -ErrorAction SilentlyContinue
    }
}

$process = $null
try {
    $process = Start-Process -FilePath $PythonPath -ArgumentList @("run.py") -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput $stdout1 -RedirectStandardError $stderr1 -PassThru
    Wait-ForHealth

    $rootResponse = Invoke-WebRequest -UseBasicParsing "$baseUrl/" -TimeoutSec 5
    if ($rootResponse.Content -notmatch "Secure first-time setup") {
        throw "Setup page content is missing"
    }
    $protectedResponse = Invoke-WebRequest -UseBasicParsing "$baseUrl/api/accounts" -TimeoutSec 5 -SkipHttpErrorCheck
    if ($protectedResponse.StatusCode -ne 503) {
        throw "Protected API did not return setup_required before setup"
    }

    $setupCodeMatch = $null
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        $combined = (Get-Content -Raw -LiteralPath $stdout1 -ErrorAction SilentlyContinue) + (Get-Content -Raw -LiteralPath $stderr1 -ErrorAction SilentlyContinue)
        $setupCodeMatch = [regex]::Match($combined, "one-time setup code:\s*([A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4})")
        if ($setupCodeMatch.Success) {
            break
        }
        Start-Sleep -Milliseconds 250
    }
    if (-not $setupCodeMatch.Success) {
        throw "One-time setup code was not found in runtime logs"
    }

    $smokePassword = "runtime smoke password 1234"
    $payload = @{
        setup_code = $setupCodeMatch.Groups[1].Value
        password = $smokePassword
    } | ConvertTo-Json
    $setup = Invoke-RestMethod -Method Post -Uri "$baseUrl/api/setup/initialize" -ContentType "application/json" -Body $payload
    if (-not $setup.success) {
        throw "Runtime setup failed"
    }

    $status = Invoke-RestMethod "$baseUrl/api/setup/status"
    if (-not $status.is_initialized) {
        throw "Setup state was not initialized"
    }

    $secretPath = Join-Path $dataRoot "secret.key"
    $databasePath = Join-Path $dataRoot "renew.db"
    if (-not (Test-Path -LiteralPath $secretPath) -or -not (Test-Path -LiteralPath $databasePath)) {
        throw "Runtime database or key was not created"
    }
    $secretHashBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath $secretPath).Hash
    $secretValue = (Get-Content -Raw -LiteralPath $secretPath).Trim()
    $combinedLogs = (Get-Content -Raw -LiteralPath $stdout1) + (Get-Content -Raw -LiteralPath $stderr1)
    if ($combinedLogs.Contains($smokePassword) -or $combinedLogs.Contains($secretValue) -or $combinedLogs -match "_code_digest|webui_password_hash") {
        throw "A sensitive runtime value appeared in logs"
    }

    Stop-SmokeProcess $process
    $process = Start-Process -FilePath $PythonPath -ArgumentList @("run.py") -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput $stdout2 -RedirectStandardError $stderr2 -PassThru
    Wait-ForHealth

    $statusAfterRestart = Invoke-RestMethod "$baseUrl/api/setup/status"
    if (-not $statusAfterRestart.is_initialized) {
        throw "Setup state did not persist across restart"
    }
    $secretHashAfter = (Get-FileHash -Algorithm SHA256 -LiteralPath $secretPath).Hash
    if ($secretHashBefore -ne $secretHashAfter) {
        throw "Generated secret did not persist across restart"
    }

    Write-Output "local runtime start/health/setup/persistence: PASS"
    Write-Output "runtime log sensitive-value check: PASS"
} finally {
    Stop-SmokeProcess $process
}
