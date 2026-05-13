$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$runtimeDir = Join-Path $repoRoot "output\runtime"
$appPidFile = Join-Path $runtimeDir "nutrition-app.pid"
$tunnelPidFile = Join-Path $runtimeDir "cloudflared.pid"
$publicUrlFile = Join-Path $runtimeDir "public-url.txt"

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
    }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

Stop-TrackedProcess -PidFile $tunnelPidFile
Stop-TrackedProcess -PidFile $appPidFile
Remove-Item $publicUrlFile -Force -ErrorAction SilentlyContinue
Write-Output "stopped"
