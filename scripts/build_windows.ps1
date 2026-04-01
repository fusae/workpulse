param(
    [string]$Python = "py -3.11",
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$ArtifactDir = "dist\artifacts"

if ($Clean) {
    if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
    if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
}

Invoke-Expression "$Python -m pip install --upgrade pip"
Invoke-Expression "$Python -m pip install .[windows,build]"
Invoke-Expression "$Python -m PyInstaller --clean --noconfirm workpulse.spec"

if (!(Test-Path "dist\workpulse.exe")) {
    throw "Expected dist\workpulse.exe was not produced."
}

New-Item -ItemType Directory -Force -Path $ArtifactDir | Out-Null
$ZipPath = Join-Path $ArtifactDir "workpulse-windows-amd64.zip"
$ExePath = Resolve-Path "dist\workpulse.exe"
$ShaPath = Join-Path $ArtifactDir "workpulse-windows-amd64.sha256"

Compress-Archive -Path $ExePath -DestinationPath $ZipPath -Force
$Hash = (Get-FileHash -Algorithm SHA256 $ExePath).Hash.ToLower()
"$Hash  workpulse.exe" | Set-Content -Path $ShaPath -Encoding ascii

Write-Host ""
Write-Host "Build complete." -ForegroundColor Green
Write-Host "EXE: dist\workpulse.exe"
Write-Host "ZIP: $ZipPath"
Write-Host "SHA256: $ShaPath"
