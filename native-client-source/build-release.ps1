$ErrorActionPreference='Stop'
$repo=Split-Path -Parent $PSScriptRoot
Set-Location $repo
$meta=Get-Content release.json -Raw | ConvertFrom-Json
$v=$meta.version
$app=Join-Path $repo 'ci-app'
$out=Join-Path $repo 'ci-output'
$installed=Join-Path $repo 'ci-installed'
foreach($dir in @($app,$out,"$app\runtime","$app\service","$app\assets\fonts")){New-Item -ItemType Directory -Force -Path $dir | Out-Null}
Copy-Item oreummok-cloud\service\*.mjs "$app\service\" -Force
Copy-Item (Get-Command node).Source "$app\runtime\node.exe" -Force
Invoke-WebRequest "https://raw.githubusercontent.com/nodejs/node/v$($meta.pcRuntime)/LICENSE" -OutFile "$app\NODE-LICENSE.txt"
$fontSpec=Get-Content assets\fonts\SOURCE.json -Raw | ConvertFrom-Json
foreach($entry in $fontSpec.files.PSObject.Properties){$file=Join-Path "$app\assets\fonts" $entry.Name;Invoke-WebRequest ("https://raw.githubusercontent.com/google/fonts/main/ofl/gothica1/"+$entry.Name) -OutFile $file;if((Get-FileHash $file -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value){throw 'Font checksum mismatch'}}
Copy-Item assets\fonts\SOURCE.json "$app\assets\fonts\SOURCE.json"
Copy-Item assets\brand\app-icon.png "$app\app-icon.png"
if((Get-FileHash "$app\app-icon.png" -Algorithm SHA256).Hash.ToLowerInvariant() -ne "5340e9ab55fb707dfa652cd79d6587c2333fad024b0633a306430c29b61f56e2"){throw "Brand icon checksum mismatch"}
Add-Type -AssemblyName System.Drawing
$bitmap=[Drawing.Bitmap]::FromFile("$app\app-icon.png")
$icon=[Drawing.Icon]::FromHandle($bitmap.GetHicon())
$stream=[IO.File]::Create("$app\oreummok.ico")
$icon.Save($stream);$stream.Dispose();$bitmap.Dispose()
Copy-Item RELEASE_1.0_ko.md "$app\RELEASE_1.0_ko.md"
Copy-Item release.json "$app\release.json"
$csc='C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$sources=@(Get-ChildItem native-client-source\desktop\*.cs | Where-Object Name -notin @('Setup.cs','InstallerCore.cs') | ForEach-Object FullName)
& $csc /nologo /target:winexe "/out:$app\OreumMok.exe" "/win32icon:$app\oreummok.ico" /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Web.Extensions.dll /reference:System.Security.dll $sources
if($LASTEXITCODE -ne 0){throw 'PC compilation failed'}
Copy-Item "$app\OreumMok.exe" "$app\OreumMokUser.exe"
$hashes=[ordered]@{}
Get-ChildItem $app -Recurse -File | ForEach-Object {$relative=$_.FullName.Substring($app.Length+1).Replace('\','/');$hashes[$relative]=(Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
$hashes | ConvertTo-Json -Depth 4 | Set-Content "$app\native-checksums.json" -Encoding utf8
$payload=Join-Path $repo 'ci-payload.zip'
Compress-Archive -Path "$app\*" -DestinationPath $payload -CompressionLevel Optimal -Force
function Compile-Installer($payloadPath,$dest){& $csc /nologo /target:winexe "/out:$dest" "/win32icon:$app\oreummok.ico" "/resource:$payloadPath,payload.zip" /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.IO.Compression.dll /reference:System.IO.Compression.FileSystem.dll /reference:System.Web.Extensions.dll /reference:Microsoft.CSharp.dll native-client-source\desktop\Setup.cs native-client-source\desktop\InstallerCore.cs native-client-source\desktop\AssemblyInfo.cs;if($LASTEXITCODE -ne 0){throw 'Installer compilation failed'}}
function Run-Checked($exe,$arguments,$seconds,$expected=0){$p=Start-Process -FilePath $exe -ArgumentList $arguments -WindowStyle Hidden -PassThru;if(!$p.WaitForExit($seconds*1000)){throw "Timed out: $exe"};if($p.ExitCode -ne $expected){throw "Unexpected exit $($p.ExitCode), expected $expected"}}
$setup="$out\OreumMokSetup-v$v.exe"
Compile-Installer $payload $setup
$installArgs=@('--silent',"--target=$installed",'--no-shortcut','--no-launch',"--log=$out\install-log.txt")
Run-Checked $setup $installArgs 90
$result=Get-Content "$installed\installation-result.json" -Raw | ConvertFrom-Json
if($result.version -ne $v -or !$result.transactional){throw 'Version or transactional installer mismatch'}
'QA user file' | Set-Content "$installed\user-note.txt"
Run-Checked $setup $installArgs 90
if((Get-Content "$installed\user-note.txt" -Raw).Trim() -ne 'QA user file'){throw 'User file lost on upgrade'}
$before=(Get-FileHash "$installed\OreumMok.exe").Hash
$env:OREUMMOK_INSTALLER_QA='1'
$env:OREUMMOK_QA_FAIL_AFTER_SWAP='1'
Run-Checked $setup $installArgs 90 1
Remove-Item Env:OREUMMOK_QA_FAIL_AFTER_SWAP
if((Get-FileHash "$installed\OreumMok.exe").Hash -ne $before -or !(Test-Path "$installed\user-note.txt")){throw 'Rollback failed'}
$env:OREUMMOK_QA_NO_SPACE='1'
Run-Checked $setup $installArgs 90 1
Remove-Item Env:OREUMMOK_QA_NO_SPACE
Remove-Item Env:OREUMMOK_INSTALLER_QA
if((Get-FileHash "$installed\OreumMok.exe").Hash -ne $before){throw 'Low-space check changed installation'}
$badApp=Join-Path $repo 'ci-bad-app'
Copy-Item $app $badApp -Recurse
Add-Content "$badApp\NODE-LICENSE.txt" 'QA corrupted file'
$badPayload=Join-Path $repo 'ci-bad-payload.zip'
Compress-Archive -Path "$badApp\*" -DestinationPath $badPayload -Force
Compile-Installer $badPayload "$out\QA-Corrupted-Installer.exe"
Run-Checked "$out\QA-Corrupted-Installer.exe" $installArgs 90 1
if((Get-FileHash "$installed\OreumMok.exe").Hash -ne $before){throw 'Corrupt payload changed installation'}
@{freshInstall=$true;upgrade=$true;userFilePreserved=$true;rollbackAfterSwap=$true;lowSpacePreserved=$true;corruptPayloadPreserved=$true} | ConvertTo-Json | Set-Content "$out\installer-validation.json"
$env:OREUMMOK_DATA_DIR=Join-Path $repo 'qa-native-release'
$env:OREUMMOK_NO_NETWORK='1'
Run-Checked "$installed\OreumMok.exe" @('--self-test') 120
& $csc /nologo /target:exe "/out:$out\NativeNetworkCheck.exe" /reference:System.Web.Extensions.dll native-client-source\NativeNetworkCheck.cs
if($LASTEXITCODE -ne 0){throw 'Network verifier compilation failed'}
Run-Checked "$out\NativeNetworkCheck.exe" @("$installed\OreumMok.exe","$out\native-cloud-check.json") 150
$client=Join-Path $repo 'ci-client'
New-Item -ItemType Directory -Force -Path $client | Out-Null
foreach($name in @('OreumMokUser.exe','app-icon.png','oreummok.ico','NODE-LICENSE.txt','RELEASE_1.0_ko.md','release.json')){Copy-Item "$app\$name" $client}
Copy-Item "$app\assets" "$client\assets" -Recurse
Compress-Archive -Path "$client\*" -DestinationPath "$out\OreumMok-User-PC-v$v.zip" -Force
Copy-Item RELEASE_1.0_ko.md "$out\RELEASE_1.0_ko.md"
$checks=[ordered]@{}
foreach($name in @("OreumMokSetup-v$v.exe","OreumMok-User-PC-v$v.zip")){$checks[$name]=(Get-FileHash "$out\$name" -Algorithm SHA256).Hash.ToLowerInvariant()}
$checks | ConvertTo-Json | Set-Content "$out\SHA256SUMS.json"
Get-Content "$out\installer-validation.json"
Get-Content "$out\native-cloud-check.json"
