$ErrorActionPreference='Stop'
$repo=Split-Path -Parent $PSScriptRoot
Set-Location $repo
$app=Join-Path $repo 'ci-app'
$out=Join-Path $repo 'ci-output'
$installed=Join-Path $repo 'ci-installed'
foreach($dir in @($app,$out,"$app\runtime","$app\service","$app\assets\fonts")){New-Item -ItemType Directory -Force -Path $dir | Out-Null}
Copy-Item oreummok-cloud\service\*.mjs "$app\service\" -Force
Copy-Item (Get-Command node).Source "$app\runtime\node.exe" -Force
Invoke-WebRequest 'https://raw.githubusercontent.com/nodejs/node/v24.11.1/LICENSE' -OutFile "$app\NODE-LICENSE.txt"
$fontSpec=Get-Content assets\fonts\SOURCE.json -Raw | ConvertFrom-Json
foreach($entry in $fontSpec.files.PSObject.Properties){$file=Join-Path "$app\assets\fonts" $entry.Name;Invoke-WebRequest ("https://raw.githubusercontent.com/google/fonts/main/ofl/gothica1/"+$entry.Name) -OutFile $file;if((Get-FileHash $file -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value){throw "Official font checksum mismatch: $($entry.Name)"}}
Copy-Item assets\fonts\SOURCE.json "$app\assets\fonts\SOURCE.json"
Add-Type -AssemblyName System.Drawing
$bitmap=New-Object System.Drawing.Bitmap 128,128
$g=[System.Drawing.Graphics]::FromImage($bitmap)
$g.SmoothingMode=[System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.Clear([System.Drawing.Color]::FromArgb(0,53,35))
$wood=New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(186,133,71))
$light=New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(244,206,137))
for($i=0;$i -lt 4;$i++){$x=16+$i*18;$y=91-$i*20;$g.FillRectangle($wood,$x,$y,52,12);$g.FillRectangle($light,$x,$y,52,3)}
$bitmap.Save("$app\app-icon.png",[System.Drawing.Imaging.ImageFormat]::Png)
$icon=[System.Drawing.Icon]::FromHandle($bitmap.GetHicon())
$stream=[System.IO.File]::Create("$app\oreummok.ico")
$icon.Save($stream)
$stream.Dispose();$g.Dispose();$bitmap.Dispose();$wood.Dispose();$light.Dispose()
Copy-Item UPGRADE_0.21_ko.md "$app\UPGRADE_0.21_ko.md"
$csc='C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$sources=@(Get-ChildItem native-client-source\desktop\*.cs | Where-Object Name -ne 'Setup.cs' | ForEach-Object FullName)
& $csc /nologo /target:winexe "/out:$app\OreumMok.exe" "/win32icon:$app\oreummok.ico" /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.Web.Extensions.dll /reference:System.Security.dll $sources
if($LASTEXITCODE -ne 0){throw 'PC compilation failed'}
Copy-Item "$app\OreumMok.exe" "$app\OreumMokUser.exe"
$hashes=[ordered]@{}
Get-ChildItem $app -Recurse -File | ForEach-Object {$relative=$_.FullName.Substring($app.Length+1).Replace('\','/');$hashes[$relative]=(Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
$hashes | ConvertTo-Json -Depth 4 | Set-Content "$app\native-checksums.json" -Encoding utf8
$payload=Join-Path $repo 'ci-payload.zip'
Compress-Archive -Path "$app\*" -DestinationPath $payload -CompressionLevel Optimal -Force
& $csc /nologo /target:winexe "/out:$out\OreumMokSetup-v0.21.exe" "/win32icon:$app\oreummok.ico" "/resource:$payload,payload.zip" /reference:System.Windows.Forms.dll /reference:System.Drawing.dll /reference:System.IO.Compression.dll /reference:System.IO.Compression.FileSystem.dll /reference:System.Web.Extensions.dll /reference:Microsoft.CSharp.dll native-client-source\desktop\Setup.cs native-client-source\desktop\AssemblyInfo.cs
if($LASTEXITCODE -ne 0){throw 'Installer compilation failed'}
function Run-Checked($exe,$arguments,$seconds){$p=Start-Process -FilePath $exe -ArgumentList $arguments -WindowStyle Hidden -PassThru;if(!$p.WaitForExit($seconds*1000)){throw "Timed out: $exe"};if($p.ExitCode -ne 0){throw "Failed exit $($p.ExitCode): $exe"}}
Run-Checked "$out\OreumMokSetup-v0.21.exe" @('--silent',"--target=$installed",'--no-shortcut','--no-launch',"--log=$out\install-log.txt") 90
$env:OREUMMOK_DATA_DIR=Join-Path $repo 'qa-native-ci-installed21'
$env:OREUMMOK_NO_NETWORK='1'
Run-Checked "$installed\OreumMok.exe" @('--self-test') 90
& $csc /nologo /target:exe "/out:$out\NativeNetworkCheck.exe" /reference:System.Web.Extensions.dll native-client-source\NativeNetworkCheck.cs
if($LASTEXITCODE -ne 0){throw 'Network verifier compilation failed'}
Run-Checked "$out\NativeNetworkCheck.exe" @("$installed\OreumMok.exe","$out\native-cloud-check.json") 150
$client=Join-Path $repo 'ci-client'
New-Item -ItemType Directory -Force -Path $client | Out-Null
foreach($name in @('OreumMokUser.exe','app-icon.png','oreummok.ico','NODE-LICENSE.txt','UPGRADE_0.21_ko.md')){Copy-Item "$app\$name" $client}
Copy-Item "$app\assets" "$client\assets" -Recurse -Force
Compress-Archive -Path "$client\*" -DestinationPath "$out\OreumMok-User-PC-v0.21.zip" -CompressionLevel Optimal -Force
Copy-Item UPGRADE_0.21_ko.md "$out\UPGRADE_0.21_ko.md"
$checks=[ordered]@{}
foreach($name in @('OreumMokSetup-v0.21.exe','OreumMok-User-PC-v0.21.zip')){$checks[$name]=(Get-FileHash "$out\$name" -Algorithm SHA256).Hash.ToLowerInvariant()}
$checks | ConvertTo-Json | Set-Content "$out\SHA256SUMS.json" -Encoding utf8
Get-Content "$out\native-cloud-check.json"
Get-Content "$installed\installation-result.json"
