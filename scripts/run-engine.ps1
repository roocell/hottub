$ErrorActionPreference = "Stop"

$repoRoot = Join-Path $PSScriptRoot ".."
$enginePath = Join-Path $repoRoot "engine"
$venvPath = Join-Path $enginePath ".venv"
$pythonExe = Join-Path (Join-Path $venvPath "Scripts") "python.exe"

if (-not (Test-Path $pythonExe)) {
  Write-Error "Venv not found. Run scripts\\setup-venv.ps1 first."
}

Set-Location $enginePath
& $pythonExe -m spa_engine
