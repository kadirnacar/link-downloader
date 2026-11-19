#!/bin/bash
# ytdlp-studio:release-sh v1
# macOS host: tüm platformlar için os_arch adlı release paketleri üretir.
set -euo pipefail

APP="ytdlp-studio"
VER="${VERSION:-1.0.0}"
OUT="release"
LDFLAGS="-w -s"

say(){ printf "\n\033[1;36m== %s\033[0m\n" "$1"; }
warn(){ printf "\033[1;33m! %s\033[0m\n" "$1"; }
die(){ printf "\033[1;31mx %s\033[0m\n" "$1"; exit 1; }

command -v go >/dev/null || die "go yok"
command -v npm >/dev/null || die "npm yok"
mkdir -p "$OUT"
rm -f "$OUT"/* 2>/dev/null || true

say "Frontend (production)"
(cd frontend && npm install --no-audit --no-fund && npm run build)
[ -f frontend/dist/index.html ] || die "frontend/dist yok"

if command -v wails3 >/dev/null; then
  say "Bindings"
  wails3 generate bindings -clean=true -ts -i || warn "bindings üretilemedi"
fi

build_go(){ # goos goarch ext cgo
  local goos="$1" goarch="$2" ext="$3" cgo="$4"
  local name="${APP}_${goos}_${goarch}${ext}"
  local flags="$LDFLAGS"
  [ "$goos" = "windows" ] && flags="$flags -H windowsgui"
  GOOS="$goos" GOARCH="$goarch" CGO_ENABLED="$cgo" \
    go build -tags production -trimpath -buildvcs=false -ldflags="$flags" -o "$OUT/$name"
  echo "  -> $OUT/$name"
}

say "macOS (darwin arm64 + amd64)"
for arch in arm64 amd64; do
  build_go darwin "$arch" "" 1
  codesign --force --sign - "$OUT/${APP}_darwin_${arch}" 2>/dev/null || true
  APPDIR="$OUT/${APP}_${arch}.app"
  rm -rf "$APPDIR"; mkdir -p "$APPDIR/Contents/MacOS" "$APPDIR/Contents/Resources"
  cp "$OUT/${APP}_darwin_${arch}" "$APPDIR/Contents/MacOS/$APP"
  [ -f build/darwin/Info.plist ] && cp build/darwin/Info.plist "$APPDIR/Contents/Info.plist"
  [ -f build/darwin/icons.icns ] && cp build/darwin/icons.icns "$APPDIR/Contents/Resources/icons.icns"
  (cd "$OUT" && zip -qry "${APP}_darwin_${arch}.app.zip" "${APP}_${arch}.app")
  if command -v hdiutil >/dev/null; then
    hdiutil create -volname "$APP" -srcfolder "$APPDIR" -ov -format UDZO \
      "$OUT/${APP}_darwin_${arch}.dmg" >/dev/null && echo "  -> ${APP}_darwin_${arch}.dmg"
  fi
  rm -rf "$APPDIR"
done

say "Windows (amd64 + arm64)"
for arch in amd64 arm64; do
  if command -v wails3 >/dev/null && [ -f build/windows/icon.ico ]; then
    wails3 generate syso -arch "$arch" -icon build/windows/icon.ico \
      -manifest build/windows/wails.exe.manifest -info build/windows/info.json \
      -out "wails_windows_${arch}.syso" 2>/dev/null || true
  fi
  build_go windows "$arch" ".exe" 0
  rm -f ./*.syso
  (cd "$OUT" && zip -qy "${APP}_windows_${arch}.zip" "${APP}_windows_${arch}.exe")
done

say "Linux (Docker: GTK4 + WebKitGTK 6.0)"
if command -v docker >/dev/null && docker info >/dev/null 2>&1; then
  for arch in amd64 arm64; do
    IMG="${APP}-linux-${arch}"
    docker build --platform "linux/${arch}" --build-arg GOARCH="$arch" \
      -t "$IMG" -f build/docker/Dockerfile.linux build/docker/ >/dev/null || { warn "$arch imajı kurulamadı"; continue; }
    docker run --rm --platform "linux/${arch}" \
      -v "$PWD:/app" -w /app \
      -v "${APP}-gomod-${arch}:/go/pkg/mod" -v "${APP}-gobuild-${arch}:/root/.cache/go-build" \
      -e CGO_ENABLED=1 -e GOOS=linux -e GOARCH="$arch" \
      "$IMG" go build -tags production -trimpath -buildvcs=false -ldflags="$LDFLAGS" \
      -o "$OUT/${APP}_linux_${arch}" || { warn "linux/$arch derlenemedi"; continue; }
    chmod +x "$OUT/${APP}_linux_${arch}"
    tar -czf "$OUT/${APP}_linux_${arch}.tar.gz" -C "$OUT" "${APP}_linux_${arch}"
    if command -v dpkg-deb >/dev/null; then
      D="$OUT/deb_${arch}"; rm -rf "$D"
      mkdir -p "$D/DEBIAN" "$D/usr/bin" "$D/usr/share/applications"
      cp "$OUT/${APP}_linux_${arch}" "$D/usr/bin/$APP"
      for s in 16 32 48 64 128 256 512; do
        src="build/linux/icons/hicolor/${s}x${s}/apps/${APP}.png"
        [ -f "$src" ] && install -Dm644 "$src" "$D/usr/share/icons/hicolor/${s}x${s}/apps/${APP}.png"
      done
      printf 'Package: %s\nVersion: %s\nArchitecture: %s\nMaintainer: ytdlp-studio\nDepends: libgtk-4-1, libwebkitgtk-6.0-4, libsoup-3.0-0\nDescription: yt-dlp desktop download studio\n' \
        "$APP" "$VER" "$arch" > "$D/DEBIAN/control"
      printf '[Desktop Entry]\nType=Application\nName=ytdlp-studio\nExec=%s\nIcon=%s\nCategories=AudioVideo;Network;\nTerminal=false\n' \
        "$APP" "$APP" > "$D/usr/share/applications/${APP}.desktop"
      dpkg-deb --build "$D" "$OUT/${APP}_linux_${arch}.deb" >/dev/null && echo "  -> ${APP}_linux_${arch}.deb"
      rm -rf "$D"
    fi
  done
else
  warn "Docker yok: Linux paketleri atlandı"
fi

say "Checksums"
(cd "$OUT" && shasum -a 256 * > checksums.txt)
ls -lh "$OUT"
say "Bitti · release/ klasörünü GitHub Release'e manuel yükleyebilirsiniz"
