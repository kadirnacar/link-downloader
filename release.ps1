# ytdlp-studio:release-ps1 v1
# Windows host: exe + zip (+ MSIX araçları varsa paket)
$ErrorActionPreference = "Stop"
$APP = "ytdlp-studio"
$OUT = "release"
New-Item -ItemType Directory -Force -Path $OUT | Out-Null

function Fail($m){ Write-Host "x $m" -ForegroundColor Red; exit 1 }
function Say($m){ Write-Host "`n== $m" -ForegroundColor Cyan }

foreach ($c in @("go","npm")) { if (-not (Get-Command $c -ErrorAction SilentlyContinue)) { Fail "$c yok" } }

Say "Frontend"
Push-Location frontend; npm install --no-audit --no-fund; npm run build; Pop-Location

if (Get-Command wails3 -ErrorAction SilentlyContinue) {
  Say "Bindings"; wails3 generate bindings -clean=true -ts -i
}

foreach ($arch in @("amd64","arm64")) {
  Say "Windows $arch"
  if ((Get-Command wails3 -ErrorAction SilentlyContinue) -and (Test-Path "build/windows/icon.ico")) {
    wails3 generate syso -arch $arch -icon build/windows/icon.ico `
      -manifest build/windows/wails.exe.manifest -info build/windows/info.json `
      -out "wails_windows_$arch.syso"
  }
  $env:GOOS="windows"; $env:GOARCH=$arch; $env:CGO_ENABLED="0"
  go build -tags production -trimpath -buildvcs=false -ldflags="-w -s -H windowsgui" `
    -o "$OUT/${APP}_windows_$arch.exe"
  if ($LASTEXITCODE -ne 0) { Fail "windows/$arch build" }
  Remove-Item Env:GOARCH -ErrorAction SilentlyContinue
  Remove-Item *.syso -ErrorAction SilentlyContinue
  Compress-Archive -Force -Path "$OUT/${APP}_windows_$arch.exe" `
    -DestinationPath "$OUT/${APP}_windows_$arch.zip"
}

if (Get-Command task -ErrorAction SilentlyContinue) {
  Say "MSIX (araçlar varsa)"
  task install:msix:tools
  task package
  if ($LASTEXITCODE -ne 0) { Write-Host "! MSIX atlandı" -ForegroundColor Yellow }
}

Say "Checksums"
Get-ChildItem $OUT -File | Get-FileHash -Algorithm SHA256 |
  ForEach-Object { "$($_.Hash.ToLower())  $(Split-Path $_.Path -Leaf)" } |
  Set-Content "$OUT/checksums.txt"
Get-ChildItem $OUT | Format-Table Name,Length -AutoSize
