# ytdlp-studio:build-all-macos v3
#!/bin/bash
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
success() { echo -e "${GREEN}✓ $1${NC}"; }
warn()    { echo -e "${YELLOW}⚠ $1${NC}"; }
error()   { echo -e "${RED}✗ $1${NC}"; exit 1; }

echo "=========================================="
echo "ytdlp-studio · macOS Host · Build All"
echo "=========================================="

command -v task   >/dev/null 2>&1 || error "Task CLI kurulu değil"
command -v docker >/dev/null 2>&1 || error "Docker kurulu değil"
docker info >/dev/null 2>&1       || error "Docker çalışmıyor"

mkdir -p bin dist/macos dist/windows-amd64 dist/windows-arm64 dist/linux-amd64

echo ""
echo "1/7 · Frontend production build (host)..."
if [ ! -d "frontend/node_modules" ]; then
  (cd frontend && npm install --no-audit --no-fund)
fi
(cd frontend && npm run build) || error "Frontend production build başarısız"
[ -f frontend/dist/index.html ] || error "frontend/dist/index.html üretilemedi"
success "frontend/dist hazır (container içinde npm çalışmayacak)"

echo ""
echo "2/7 · Docker imajları hazırlanıyor..."
task setup:docker || warn "wails-cross imajı kurulamadı (Windows build native olduğu için devam ediliyor)"
echo "Linux builder imajı (GTK4 + WebKitGTK 6.0) hazırlanıyor..."
docker build --platform linux/amd64 \
  -t ytdlp-linux-builder \
  -f build/docker/Dockerfile.linux build/docker/ || error "Linux builder imajı build edilemedi"
success "Docker imajları hazır"

echo ""
echo "3/7 · macOS build (native)..."
task build || error "macOS build başarısız"
cp -f bin/ytdlp-studio dist/macos/ 2>/dev/null || true
success "macOS → dist/macos/ytdlp-studio"

echo ""
echo "4/7 · Windows amd64 build..."
GOOS=windows GOARCH=amd64 task build || error "Windows amd64 build başarısız"
cp -f bin/ytdlp-studio.exe dist/windows-amd64/
success "Windows amd64 → dist/windows-amd64/"

echo ""
echo "5/7 · Windows arm64 build..."
GOOS=windows GOARCH=arm64 task build || error "Windows arm64 build başarısız"
cp -f bin/ytdlp-studio.exe dist/windows-arm64/
success "Windows arm64 → dist/windows-arm64/"

echo ""
echo "6/7 · Linux amd64 build (Docker x86_64 · GTK4/WebKitGTK6)..."
docker run --rm --platform linux/amd64 \
  -v "$PWD:/app" -w /app \
  -v ytdlp-go-mod:/go/pkg/mod \
  -v ytdlp-go-build:/root/.cache/go-build \
  -e CGO_ENABLED=1 -e GOOS=linux -e GOARCH=amd64 \
  ytdlp-linux-builder \
  go build -tags production -trimpath -buildvcs=false -ldflags="-w -s" -o bin/ytdlp-studio-linux-amd64 \
  || error "Linux amd64 build başarısız"
cp -f bin/ytdlp-studio-linux-amd64 dist/linux-amd64/ytdlp-studio
chmod +x dist/linux-amd64/ytdlp-studio
if command -v file >/dev/null 2>&1; then
  file dist/linux-amd64/ytdlp-studio | grep -q "ELF 64-bit" \
    && success "Linux binary ELF 64-bit olarak doğrulandı" \
    || warn "Linux binary mimarisi doğrulanamadı"
fi
success "Linux amd64 → dist/linux-amd64/ytdlp-studio"

echo ""
echo "7/7 · Temizlik..."
rm -f bin/ytdlp-studio-linux-amd64

echo ""
echo "=========================================="
success "Tüm platformlar için build tamamlandı!"
echo ""
ls -lh dist/*/ 2>/dev/null || true
echo ""
echo "Linux hedef makinede çalışma zamanı gereksinimleri:"
echo "  sudo apt install libgtk-4-1 libwebkitgtk-6.0-4 libsoup-3.0-0"
