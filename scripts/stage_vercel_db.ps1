param(
    [string]$SourceDbPath = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
if ($SourceDbPath) {
    python (Join-Path $PSScriptRoot "stage_vercel_db.py") $SourceDbPath
    exit $LASTEXITCODE
}

python (Join-Path $PSScriptRoot "stage_vercel_db.py")
exit $LASTEXITCODE
