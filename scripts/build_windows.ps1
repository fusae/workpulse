param(
    [string]$Python = "py -3.11",
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

if ($Clean) {
    if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
    if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
}

Invoke-Expression "$Python -m pip install --upgrade pip"
Invoke-Expression "$Python -m pip install .[windows,build]"
Invoke-Expression "$Python -m PyInstaller --clean workpulse.spec"

Write-Host ""
Write-Host "Build complete. Binary is in dist\workpulse\" -ForegroundColor Green
