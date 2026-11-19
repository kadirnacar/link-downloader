#!/bin/bash
set -e

echo "=========================================="
echo "ytdlp-studio · Tüm Platformlar İçin Build"
echo "=========================================="

# Renk kodları
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

success() {
    echo -e "${GREEN}✓ $1${NC}"
}

warn() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

error() {
    echo -e "${RED}✗ $1${NC}"
    exit 1
}

# Ön kontroller
command -v task >/dev/null 2>&1 || error "Task CLI kurulu değil. 'brew install go-task' ile kurun."
command -v docker >/dev/null 2>&1 || error "Docker kurulu değil."
docker info >/dev/null 2>&1 || error "Docker çalışmıyor."

echo ""
echo "1/6 · Docker imajı kuruluyor (cross-compile için)..."
task setup:docker || error "Docker imajı build edilemedi"
success "Docker imajı hazır"

echo ""
echo "2/6 · Frontend bağımlılıkları kontrol ediliyor..."
if [ ! -d "frontend/node_modules" ]; then
    cd frontend && npm install && cd ..
fi
success "Frontend hazır"

echo ""
echo "3/6 · macOS build (native)..."
task build || error "macOS build başarısız"
success "macOS: bin/ytdlp-studio"

echo ""
echo "4/6 · Windows amd64 build..."
GOOS=windows GOARCH=amd64 task build || error "Windows amd64 build başarısız"
success "Windows amd64: bin/ytdlp-studio.exe"

echo ""
echo "5/6 · Windows arm64 build..."
GOOS=windows GOARCH=arm64 task build || error "Windows arm64 build başarısız"
success "Windows arm64: bin/ytdlp-studio.exe"

echo ""
echo "6/6 · Linux amd64 build (Docker cross-compile)..."
GOOS=linux GOARCH=amd64 task build || error "Linux amd64 build başarısız"
success "Linux amd64: bin/ytdlp-studio"

echo ""
echo "7/6 · Linux arm64 build (Docker cross-compile)..."
GOOS=linux GOARCH=arm64 task build || error "Linux arm64 build başarısız"
success "Linux arm64: bin/ytdlp-studio"

echo ""
echo "=========================================="
echo "Tüm platformlar için build tamamlandı!"
echo "=========================================="
echo ""
echo "Çıktılar:"
ls -lh bin/ 2>/dev/null || warn "bin/ dizini bulunamadı"
echo ""
echo "Sonraki adımlar:"
echo "  - macOS paketleme: task package"
echo "  - Windows MSIX: Windows makinesinde 'task package'"
echo "  - Linux paketleme: GOOS=linux task package"
