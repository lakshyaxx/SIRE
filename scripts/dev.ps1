$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $repoRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Install the documented Python environment first; see README.md.'
}
& $pythonPath (Join-Path $PSScriptRoot 'dev.py')
exit $LASTEXITCODE
