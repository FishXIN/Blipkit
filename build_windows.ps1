param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$Venv = ".venv-win"
$Python = Join-Path $Venv "Scripts\python.exe"
$PyInstaller = Join-Path $Venv "Scripts\pyinstaller.exe"

if (-not (Test-Path $Python)) {
    python -m venv $Venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create build environment" }
}
if (-not $SkipInstall) {
    & $Python -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "Could not upgrade pip" }
    & $Python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "Could not install build dependencies" }
}
# Avoid a traceback probe: Windows PowerShell treats redirected native stderr
# as a terminating error before the missing dependency can be installed.
& $Python -c "import importlib.util, sys; sys.exit(importlib.util.find_spec('tinysoundfont') is None)"
if ($LASTEXITCODE -ne 0) {
    & $Python -m pip install --no-deps "tinysoundfont==0.3.7"
    if ($LASTEXITCODE -ne 0) { throw "Could not install sampled-instrument renderer" }
}

$VersionOutput = & $Python -c "from blipkit import __version__; print(__version__)"
if ($LASTEXITCODE -ne 0) { throw "Could not read application version" }
$Version = $VersionOutput.Trim()
$Arch = if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { "arm64" } else { "x64" }
$env:PYINSTALLER_CONFIG_DIR = Join-Path $PWD ".pyinstaller"
$Icon = Join-Path $PWD "assets\icon.ico"
$IconPng = Join-Path $PWD "assets\icon.png"
$SoundFonts = Join-Path $PWD "assets\soundfonts"

Remove-Item -Recurse -Force build\windows, dist\windows -ErrorAction SilentlyContinue
& $PyInstaller main.py `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name Blipkit `
    --paths src `
    --icon $Icon `
    --add-data "$IconPng;assets" `
    --add-data "$SoundFonts;assets\soundfonts" `
    --collect-all customtkinter `
    --collect-all tinysoundfont `
    --hidden-import soundfile `
    --hidden-import lameenc `
    --exclude-module matplotlib `
    --exclude-module scipy `
    --exclude-module pandas `
    --distpath dist\windows `
    --workpath build\windows `
    --specpath build\windows
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

$Source = "dist\windows\Blipkit"
$Release = "dist\Blipkit-windows-$Arch"
Remove-Item -Recurse -Force $Release -ErrorAction SilentlyContinue
Copy-Item -Recurse -Force $Source $Release

$Zip = "dist\Blipkit-$Version-windows-$Arch.zip"
Remove-Item -Force $Zip -ErrorAction SilentlyContinue
Compress-Archive -Path "$Release\*" -DestinationPath $Zip -Force

$Hash = Get-FileHash -Algorithm SHA256 $Zip
"$($Hash.Hash.ToLower())  $([IO.Path]::GetFileName($Zip))" |
    Set-Content -Path "dist\checksums-windows.txt" -Encoding ascii

Write-Host "Built $Release"
Write-Host "Archive $Zip"
