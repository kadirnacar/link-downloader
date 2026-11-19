# ytdlp-studio:build-all-macos v2
#!/bin/bash
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
success() { echo -e "${GREEN}✓ $1${NC}"; }
warn()    { echo -e "${YELLOW}⚠ $1${NC}"; }
error()   { echo -e "${RED}✗ $1${NC}"; exit 1; }

echo "=========================================="
echo "ytdlp-studio · macOS Host · Build All"
echo "=========================================="

command -v task >/dev/null 2>&1 || error "Task CLI kurulu değil"
command -v docker >/dev/null 2>&1 || error "Docker kurulu değil"
docker info >/dev/null 2>&1 || error "Docker çalışmıyor"

mkdir -p bin dist/windows-amd64 dist/windows-arm64 dist/linux-amd64 dist/macos

echo ""
echo "1/7 · Frontend bağımlılıkları..."
if [ ! -d "frontend/node_modules" ]; then
  (cd frontend && npm install)
fi
success "Frontend hazır"

echo ""
echo "2/7 · Docker imajları hazırlanıyor..."
task setup:docker || error "wails-cross imajı build edilemedi"

if [ ! "$(docker images -q ytdlp-linux-builder 2> /dev/null)" ]; then
  echo "Linux builder imajı oluşturuluyor (ilk seferde yavaş olabilir)..."
  docker build --platform linux/amd64 -t ytdlp-linux-builder -f build/docker/Dockerfile.linux build/docker/ || error "Linux builder imajı build edilemedi"
fi
success "Docker imajları hazır"

echo ""
echo "3/7 · macOS build (native)..."
task build || error "macOS build başarısız"
cp -f bin/ytdlp-studio dist/macos/ 2>/dev/null || true
success "macOS → bin/ytdlp-studio"

echo ""
echo "4/7 · Windows amd64 build (wails-cross)..."
GOOS=windows GOARCH=amd64 task build || error "Windows amd64 build başarısız"
cp -f bin/ytdlp-studio.exe dist/windows-amd64/
success "Windows amd64 → dist/windows-amd64/"

echo ""
echo "5/7 · Windows arm64 build (wails-cross)..."
GOOS=windows GOARCH=arm64 task build || error "Windows arm64 build başarısız"
cp -f bin/ytdlp-studio.exe dist/windows-arm64/
success "Windows arm64 → dist/windows-arm64/"

echo ""
echo "6/7 · Linux amd64 build (Docker x86_64 emulation)..."
docker run --rm --platform linux/amd64 \
  -v "$PWD:/app" -w /app \
  -e CGO_ENABLED=1 \
  ytdlp-linux-builder \
  bash -c "cd frontend && npm install --silent && cd .. && go build -tags production -trimpath -buildvcs=false -ldflags='-w -s' -o bin/ytdlp-studio-linux-amd64" || error "Linux amd64 build başarısız"
cp -f bin/ytdlp-studio-linux-amd64 dist/linux-amd64/ytdlp-studio
success "Linux amd64 → dist/linux-amd64/"

echo ""
echo "7/7 · Temizlik..."
rm -f bin/ytdlp-studio-linux-amd64

echo ""
echo "=========================================="
success "Tüm platformlar için build tamamlandı!"
echo ""
echo "Çıktılar:"
ls -lh dist/*/ 2>/dev/null || true
