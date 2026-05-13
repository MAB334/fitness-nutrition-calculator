param(
    [int]$Port = 8010
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$runtimeDir = Join-Path $repoRoot "output\runtime"
$appPidFile = Join-Path $runtimeDir "nutrition-app-lan.pid"
$appOutFile = Join-Path $runtimeDir "nutrition-app-lan.out.log"
$appErrFile = Join-Path $runtimeDir "nutrition-app-lan.err.log"

New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

function Test-ProcessAlive([int]$ProcessId) {
    try {
        Get-Process -Id $ProcessId -ErrorAction Stop | Out-Null
        return $true
    } catch {
        return $false
    }
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

$listenPid = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1 -ExpandProperty OwningProcess
if ($listenPid) {
    Stop-Process -Id $listenPid -Force
    Start-Sleep -Milliseconds 500
}

$pythonExe = Find-PythonCommand
$process = Start-Process `
    -FilePath $pythonExe `
    -ArgumentList @("-m", "nutrition_app", "--host", "0.0.0.0", "--port", $Port) `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput $appOutFile `
    -RedirectStandardError $appErrFile `
    -WindowStyle Hidden `
    -PassThru

Set-Content -Path $appPidFile -Value $process.Id
Wait-ForHealth -HealthUrl "http://127.0.0.1:$Port/api/health"

$addresses = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object {
        $_.IPAddress -notlike "127.*" -and
        $_.IPAddress -notlike "169.254.*" -and
        $_.IPAddress -notlike "172.17.*" -and
        $_.IPAddress -notlike "172.18.*" -and
        $_.IPAddress -notlike "172.19.*" -and
        $_.IPAddress -notlike "172.20.*"
    } |
    Sort-Object InterfaceMetric, SkipAsSource, IPAddress

if (-not $addresses) {
    Write-Output "http://127.0.0.1:$Port/"
    exit 0
}

$urls = foreach ($address in $addresses) {
    "http://$($address.IPAddress):$Port/"
}

foreach ($url in ($urls | Select-Object -Unique)) {
    Write-Output $url
}
