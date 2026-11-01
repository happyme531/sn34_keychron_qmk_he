# Compatibility entry; both commands now use the same QMK Make backend.
param([Parameter(ValueFromRemainingArguments=$true)][string[]]$BuildArguments)
$ErrorActionPreference = 'Stop'
& uv run (Join-Path $PSScriptRoot 'build_bat68.py') --build-dir build/bat68_make @BuildArguments
exit $LASTEXITCODE
