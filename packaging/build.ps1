param([switch]$SkipFreeze,[string]$CompilerPath)
$ErrorActionPreference='Stop'
$taskRoot=Split-Path $PSScriptRoot -Parent
$taskPython=Join-Path $taskRoot '.build-env\Scripts\python.exe'
$taskCompiler=Join-Path $taskRoot '.build-tools\InnoSetup\ISCC.exe'
if ($CompilerPath) {$taskCompiler=$CompilerPath}
if (-not (Test-Path -LiteralPath $taskPython)) {throw 'Build environment missing; see packaging/BUILD.md.'}
if (-not (Test-Path -LiteralPath $taskCompiler)) {throw 'Inno Setup compiler missing; see packaging/BUILD.md.'}
if (-not $SkipFreeze) {
    & $taskPython -m PyInstaller --noconfirm --distpath (Join-Path $taskRoot 'dist') --workpath (Join-Path $taskRoot '.build-work') (Join-Path $PSScriptRoot 'FlyWire-Pong.spec')
    if ($LASTEXITCODE -ne 0) {throw 'Executable build failed'}
}
& $taskCompiler (Join-Path $PSScriptRoot 'installer.iss')
if ($LASTEXITCODE -ne 0) {throw 'Installer build failed'}
$taskFile=Join-Path $taskRoot 'release\FlyWire-Pong-Setup-1.0.0-Windows-x64.exe'
$taskHash=(Get-FileHash -LiteralPath $taskFile -Algorithm SHA256).Hash.ToLowerInvariant()
[IO.File]::WriteAllText((Join-Path $taskRoot 'release\SHA256SUMS.txt'),($taskHash+'  '+[IO.Path]::GetFileName($taskFile)+[Environment]::NewLine),(New-Object Text.UTF8Encoding($false)))
Get-Item -LiteralPath $taskFile | Select-Object FullName,Length
