$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$targetDb = Join-Path $repoRoot "nutrition_app\data\china_nutrition.db"

if (Test-Path $targetDb) {
    Remove-Item -LiteralPath $targetDb -Force
}

Write-Output "cleaned"
