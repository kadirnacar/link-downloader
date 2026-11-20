# ytdlp-studio:build-all-linux v1
#!/bin/bash
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
success() { echo -e "${GREEN}✓ $1${NC}"; }
warn()    { echo -e "${YELLOW}⚠ $1${NC}"; }
error()   { echo -e "${RED}✗ $1${NC}"; exit 1; }

echo "=========================================="
echo "ytdlp-studio · Linux Host · Build All"
echo "=========================================="

command -v task >/dev/null 2>&1 || error "Task CLI kurulu değil (brew/go install github.com/go-task/task/v3/cmd/task@latest)"
command -v go   >/dev/null 2>&1 || error "Go kurulu değil (>= 1.27)"
command -v npm  >/dev/null 2>&1 || error "npm kurulu değil"

HAS_DOCKER=0
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then HAS_DOCKER=1; fi

# Native Linux GUI build için WebKitGTK dev paketleri (CGO) şart
if ! pkg-config --exists gtk4 webkitgtk-6.0 libsoup-3.0 2>/dev/null; then
  echo "GTK4 / WebKitGTK 6.0 / libsoup-3.0 geliştirme paketleri bulunamadı:"
  echo "  Debian/Ubuntu: sudo apt install libgtk-4-dev libwebkitgtk-6.0-dev libsoup-3.0-dev build-essential pkg-config"
  echo "  Fedora:        sudo dnf install gtk4-devel webkitgtk6.0-devel libsoup3-devel pkg-config"
  echo "  Arch:          sudo pacman -S gtk4 webkitgtk-6.0 libsoup3 pkg-config base-devel"
  error "Wails v3 Linux build için GTK4 + WebKitGTK 6.0 + libsoup-3.0 dev paketleri gerekli"
fi

mkdir -p dist/linux-amd64 dist/linux-arm64 dist/windows-amd64 dist/windows-arm64

echo ""
echo "1/6 · Frontend bağımlılıkları..."
if [ ! -d "frontend/node_modules" ]; then
  (cd frontend && npm install)
fi
success "Frontend hazır"

echo ""
echo "2/6 · Linux amd64 (native)..."
task build || error "Linux amd64 build başarısız"
cp -f bin/ytdlp-studio dist/linux-amd64/
success "Linux amd64 → dist/linux-amd64/ytdlp-studio"

echo ""
echo "3/6 · Windows amd64 (cross, CGO'suz)..."
GOOS=windows GOARCH=amd64 task build || error "Windows amd64 build başarısız"
cp -f bin/ytdlp-studio.exe dist/windows-amd64/
success "Windows amd64 → dist/windows-amd64/ytdlp-studio.exe"

echo ""
echo "4/6 · Windows arm64 (cross)..."
GOOS=windows GOARCH=arm64 task build || error "Windows arm64 build başarısız"
cp -f bin/ytdlp-studio.exe dist/windows-arm64/
success "Windows arm64 → dist/windows-arm64/ytdlp-studio.exe"

echo ""
echo "5/6 · Linux arm64 (Docker cross)..."
if [ "$HAS_DOCKER" -eq 1 ]; then
  task setup:docker
  GOOS=linux GOARCH=arm64 task build || warn "Linux arm64 build başarısız (atlandı)"
  if [ -f bin/ytdlp-studio ]; then cp -f bin/ytdlp-studio dist/linux-arm64/; success "Linux arm64 → dist/linux-arm64/"; fi
else
  warn "Docker çalışmıyor: Linux arm64 cross-build atlandı"
fi

echo ""
echo "6/6 · Linux paketleme (AppImage/deb · build/linux/Taskfile.yml)..."
GOOS=linux task package || warn "Linux paketleme başarısız (binary'ler yine de hazır)"

echo ""
echo "=========================================="
success "Build tamamlandı"
ls -lh bin/ 2>/dev/null || true
ls -lh dist/*/ 2>/dev/null || true
echo ""
echo "Notlar:"
echo "  - Windows MSIX paketi yalnızca Windows'ta: task install:msix:tools && task package"
echo "  - macOS hedefi (opsiyonel, Docker imajı SDK içerir): GOOS=darwin task build"
