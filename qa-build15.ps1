$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
Set-Location $root
Copy-Item native\app\OreumMok.exe native\app\OreumMokUser.exe -Force
Copy-Item native\service\* native\app\service\ -Force
$env:OREUMMOK_DATA_DIR=Join-Path $root 'native\qa-native15'
$env:OREUMMOK_NO_NETWORK='1'
$p=Start-Process -FilePath (Join-Path $root 'native\app\OreumMok.exe') -ArgumentList '--self-test' -WindowStyle Hidden -PassThru
if(!$p.WaitForExit(55000)){throw 'Windows QA timeout'}
if($p.ExitCode -ne 0){throw "Windows QA exit $($p.ExitCode)"}
Write-Output 'Windows installed-layout and native bridge checks passed'
