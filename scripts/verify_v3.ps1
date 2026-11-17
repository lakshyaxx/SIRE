$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
& (Join-Path $repoRoot '.venv/Scripts/python.exe') (Join-Path $PSScriptRoot 'verify_v3.py') @args
exit $LASTEXITCODE
