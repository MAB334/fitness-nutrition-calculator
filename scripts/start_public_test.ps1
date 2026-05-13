param(
    [int]$Port = 8010,
    [string]$LocalHost = "127.0.0.1"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$runtimeDir = Join-Path $repoRoot "output\runtime"
$toolDir = Join-Path $repoRoot ".tools\cloudflared"
$cloudflaredExe = Join-Path $toolDir "cloudflared.exe"
$cloudflaredDownloadUrl = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
$appPidFile = Join-Path $runtimeDir "nutrition-app.pid"
$tunnelPidFile = Join-Path $runtimeDir "cloudflared.pid"
$publicUrlFile = Join-Path $runtimeDir "public-url.txt"
$appOutFile = Join-Path $runtimeDir "nutrition-app.out.log"
$appErrFile = Join-Path $runtimeDir "nutrition-app.err.log"
$tunnelOutFile = Join-Path $runtimeDir "cloudflared.out.log"
$tunnelErrFile = Join-Path $runtimeDir "cloudflared.err.log"

New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
New-Item -ItemType Directory -Force -Path $toolDir | Out-Null

function Test-ProcessAlive([int]$ProcessId) {
    try {
        Get-Process -Id $ProcessId -ErrorAction Stop | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Stop-TrackedProcess([string]$PidFile) {
    if (-not (Test-Path $PidFile)) {
        return
    }
    $trackedPid = Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($trackedPid -and $trackedPid -match '^\d+$' -and (Test-ProcessAlive -ProcessId ([int]$trackedPid))) {
        Stop-Process -Id ([int]$trackedPid) -Force
        Start-Sleep -Milliseconds 300
    }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

function Find-PythonCommand {
    foreach ($candidate in @("python", "py")) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($command) {
            return $command.Source
        }
    }
    throw "Python executable not found in PATH."
}

function Wait-ForHealth([string]$HealthUrl, [int]$TimeoutSeconds = 30) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing $HealthUrl -TimeoutSec 3
            if ($response.StatusCode -eq 200) {
                return
            }
        } catch {
        }
        Start-Sleep -Milliseconds 500
    }
    throw "App health check failed: $HealthUrl"
}

function Ensure-Cloudflared {
    if ((Test-Path $cloudflaredExe) -and ((Get-Item $cloudflaredExe).Length -gt 0)) {
        return
    }
    Remove-Item $cloudflaredExe -Force -ErrorAction SilentlyContinue
    & curl.exe -L $cloudflaredDownloadUrl -o $cloudflaredExe | Out-Null
    if (-not (Test-Path $cloudflaredExe) -or ((Get-Item $cloudflaredExe).Length -le 0)) {
        throw "cloudflared download failed."
    }
}

function Ensure-AppServer {
    $healthUrl = "http://$LocalHost`:$Port/api/health"
    try {
        $response = Invoke-WebRequest -UseBasicParsing $healthUrl -TimeoutSec 3
        if ($response.StatusCode -eq 200) {
            return
        }
    } catch {
    }

    $pythonExe = Find-PythonCommand
    $process = Start-Process `
        -FilePath $pythonExe `
        -ArgumentList @("-m", "nutrition_app", "--host", $LocalHost, "--port", $Port) `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $appOutFile `
        -RedirectStandardError $appErrFile `
        -WindowStyle Hidden `
        -PassThru
    Set-Content -Path $appPidFile -Value $process.Id
    Wait-ForHealth -HealthUrl $healthUrl
}

function Wait-ForPublicUrl([int]$TimeoutSeconds = 45) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $pattern = 'https://[-a-z0-9]+\.trycloudflare\.com'
    while ((Get-Date) -lt $deadline) {
        foreach ($file in @($tunnelOutFile, $tunnelErrFile)) {
            if (-not (Test-Path $file)) {
                continue
            }
            $content = Get-Content $file -Raw -ErrorAction SilentlyContinue
            if ($content -match $pattern) {
                return $Matches[0]
            }
        }
        Start-Sleep -Milliseconds 500
    }
    throw "Cloudflare public URL was not found in time."
}

Stop-TrackedProcess -PidFile $tunnelPidFile
Ensure-Cloudflared
Ensure-AppServer

Remove-Item $publicUrlFile, $tunnelOutFile, $tunnelErrFile -Force -ErrorAction SilentlyContinue

$tunnelProcess = Start-Process `
    -FilePath $cloudflaredExe `
    -ArgumentList @("tunnel", "--url", "http://$LocalHost`:$Port", "--no-autoupdate") `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput $tunnelOutFile `
    -RedirectStandardError $tunnelErrFile `
    -WindowStyle Hidden `
    -PassThru

Set-Content -Path $tunnelPidFile -Value $tunnelProcess.Id
$publicUrl = Wait-ForPublicUrl
Set-Content -Path $publicUrlFile -Value $publicUrl
Write-Output $publicUrl
