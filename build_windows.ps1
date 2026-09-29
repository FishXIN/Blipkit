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
}
if (-not $SkipInstall) {
    & $Python -m pip install --upgrade pip
    & $Python -m pip install -r requirements.txt
}

$Version = (& $Python -c "from blipkit import __version__; print(__version__)").Trim()
$Arch = if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { "arm64" } else { "x64" }
$env:PYINSTALLER_CONFIG_DIR = Join-Path $PWD "build\.pyinstaller"
$Icon = Join-Path $PWD "assets\icon.ico"
$IconPng = Join-Path $PWD "assets\icon.png"

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
    --collect-all customtkinter `
    --hidden-import soundfile `
    --hidden-import lameenc `
    --exclude-module matplotlib `
    --exclude-module scipy `
    --exclude-module pandas `
    --distpath dist\windows `
    --workpath build\windows `
    --specpath build\windows

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
