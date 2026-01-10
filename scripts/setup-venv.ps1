$ErrorActionPreference = "Stop"

$repoRoot = Join-Path $PSScriptRoot ".."
$enginePath = Join-Path $repoRoot "engine"
$venvPath = Join-Path $enginePath ".venv"
$reqPath = Join-Path $enginePath "requirements.txt"

python -m venv $venvPath
$pythonExe = Join-Path (Join-Path $venvPath "Scripts") "python.exe"
$pipExe = Join-Path (Join-Path $venvPath "Scripts") "pip.exe"
& $pythonExe -m pip install --upgrade pip
& $pipExe install -r $reqPath

Write-Host "Venv ready at $venvPath"
