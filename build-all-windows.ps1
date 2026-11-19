# ytdlp-studio:build-all-windows v1
# PowerShell 5.1+ uyumlu · Windows host için tüm platform build'leri
$ErrorActionPreference = "Stop"

function Success($m) { Write-Host ("OK  " + $m) -ForegroundColor Green }
function Warn($m)    { Write-Host ("WARN " + $m) -ForegroundColor Yellow }
function Fail($m)    { Write-Host ("ERR " + $m) -ForegroundColor Red; exit 1 }

Write-Host "=========================================="
Write-Host "ytdlp-studio - Windows Host - Build All"
Write-Host "=========================================="

foreach ($cmd in @("task", "go", "npm")) {
  if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { Fail "$cmd kurulu değil" }
}

$HasDocker = $false
if (Get-Command docker -ErrorAction SilentlyContinue) {
  docker info *> $null
  if ($LASTEXITCODE -eq 0) { $HasDocker = $true }
}

New-Item -ItemType Directory -Force -Path "dist/windows-amd64", "dist/windows-arm64", "dist/linux-amd64", "dist/linux-arm64" | Out-Null

Write-Host ""
Write-Host "1/6 - Frontend bagimliliklari..."
if (-not (Test-Path "frontend/node_modules")) {
  Push-Location frontend; npm install; Pop-Location
}
Success "Frontend hazir"

Write-Host ""
Write-Host "2/6 - Windows amd64 (native)..."
task build
if ($LASTEXITCODE -ne 0) { Fail "Windows amd64 build basarisiz" }
Copy-Item "bin/ytdlp-studio.exe" "dist/windows-amd64/" -Force
Success "Windows amd64 -> dist/windows-amd64/"

Write-Host ""
Write-Host "3/6 - Windows arm64..."
$env:GOOS = "windows"; $env:GOARCH = "arm64"
task build
$rc = $LASTEXITCODE
Remove-Item Env:GOARCH -ErrorAction SilentlyContinue
if ($rc -ne 0) { Fail "Windows arm64 build basarisiz" }
Copy-Item "bin/ytdlp-studio.exe" "dist/windows-arm64/" -Force
Success "Windows arm64 -> dist/windows-arm64/"

Write-Host ""
Write-Host "4/6 - Linux amd64 (Docker cross)..."
if ($HasDocker) {
  task setup:docker
  $env:GOOS = "linux"; $env:GOARCH = "amd64"
  task build
  $rc = $LASTEXITCODE
  if ($rc -eq 0) { Copy-Item "bin/ytdlp-studio" "dist/linux-amd64/" -Force; Success "Linux amd64 -> dist/linux-amd64/" }
  Remove-Item Env:GOOS -ErrorAction SilentlyContinue; Remove-Item Env:GOARCH -ErrorAction SilentlyContinue
  if ($rc -ne 0) { Warn "Linux amd64 build basarisiz (atlandi)" }
} else {
  Warn "Docker calismiyor: Linux cross-build atlandi"
}

Write-Host ""
Write-Host "5/6 - Linux arm64 (Docker cross)..."
if ($HasDocker) {
  $env:GOOS = "linux"; $env:GOARCH = "arm64"
  task build
  $rc = $LASTEXITCODE
  if ($rc -eq 0) { Copy-Item "bin/ytdlp-studio" "dist/linux-arm64/" -Force; Success "Linux arm64 -> dist/linux-arm64/" }
  Remove-Item Env:GOOS -ErrorAction SilentlyContinue; Remove-Item Env:GOARCH -ErrorAction SilentlyContinue
  if ($rc -ne 0) { Warn "Linux arm64 build basarisiz (atlandi)" }
} else {
  Warn "Docker calismiyor: Linux arm64 atlandi"
}

Write-Host ""
Write-Host "6/6 - Windows MSIX paket..."
task install:msix:tools
task package
if ($LASTEXITCODE -ne 0) { Warn "MSIX paketleme basarisiz (binary'ler yine de hazir)" } else { Success "MSIX paketi uretildi" }

Write-Host ""
Write-Host "=========================================="
Success "Build tamamlandi"
Get-ChildItem -Recurse "dist" | Select-Object FullName, Length | Format-Table -AutoSize
Write-Host "Notlar:"
Write-Host "  - Linux native GUI build WebKitGTK gerektirir; cross-build Docker imaji bunu icinde cozumler."
Write-Host "  - macOS hedefi (opsiyonel): GOOS=darwin task build (Docker imaji SDK icerir)"
