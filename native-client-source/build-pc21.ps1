# Backward-compatible manual entry point.
& (Join-Path $PSScriptRoot 'build-release.ps1')
if($LASTEXITCODE -ne 0){exit $LASTEXITCODE}
