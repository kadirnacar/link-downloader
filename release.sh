#!/bin/bash
# ytdlp-studio:release-sh v2
# macOS host · os_arch adlı release paketleri + DOĞRU .app imzalama/notarization
set -euo pipefail

APP="ytdlp-studio"
DISPLAY_NAME="ytdlp-studio"
VER="${VERSION:-1.0.0}"
OUT="release"
WORK="build/_release"
IDENTITY="${CODESIGN_IDENTITY:--}"          # "-" = ad-hoc; Developer ID Application: ... önerilir
export MACOSX_DEPLOYMENT_TARGET="${MACOSX_DEPLOYMENT_TARGET:-13.0}"
LDFLAGS="-w -s"

say(){ printf "\n\033[1;36m== %s\033[0m\n" "$1"; }
warn(){ printf "\033[1;33m! %s\033[0m\n" "$1"; }
die(){ printf "\033[1;31mx %s\033[0m\n" "$1"; exit 1; }

command -v go >/dev/null || die "go yok"
command -v npm >/dev/null || die "npm yok"
command -v codesign >/dev/null || die "codesign yok (Xcode CLT kurun)"

[ -f build/darwin/Info.plist ] || die "build/darwin/Info.plist yok (apply_branding_macos_fix.py çalıştırın)"
[ -f build/darwin/icons.icns ] || die "build/darwin/icons.icns yok"

rm -rf "$OUT" "$WORK"; mkdir -p "$OUT" "$WORK"

say "Frontend (production)"
(cd frontend && npm install --no-audit --no-fund && npm run build)
[ -f frontend/dist/index.html ] || die "frontend/dist yok"

if command -v wails3 >/dev/null; then
  say "Bindings"
  wails3 generate bindings -clean=true -ts -i || warn "bindings üretilemedi"
fi

sign_target(){ # path
  local target="$1"
  xattr -cr "$target" 2>/dev/null || true
  if [ "$IDENTITY" = "-" ]; then
    codesign --force --deep --sign - "$target"
  else
    codesign --force --deep --options runtime --timestamp --sign "$IDENTITY" "$target"
  fi
  codesign --verify --deep --strict "$target" || die "imza doğrulanamadı: $target"
}

notarize_app(){ # app_path
  local app="$1"
  if [ "$IDENTITY" = "-" ]; then
    warn "Ad-hoc imza: notarization yapılamaz. DMG içindeki 'Kurulum.command' quarantine'i temizler."
    return 0
  fi
  if [ -z "${APPLE_ID:-}" ] || [ -z "${APPLE_TEAM_ID:-}" ] || [ -z "${APPLE_APP_PASSWORD:-}" ]; then
    warn "APPLE_ID / APPLE_TEAM_ID / APPLE_APP_PASSWORD yok: notarization atlandı"
    return 0
  fi
  say "Notarization: $(basename "$app")"
  local zip="$WORK/notarize.zip"
  rm -f "$zip"
  ditto -c -k --keepParent "$app" "$zip"
  xcrun notarytool submit "$zip" --apple-id "$APPLE_ID" --team-id "$APPLE_TEAM_ID" \
    --password "$APPLE_APP_PASSWORD" --wait || die "notarization başarısız"
  xcrun stapler staple "$app" || warn "staple başarısız"
  xcrun stapler validate "$app" || true
}

make_app(){ # goarch binary_path -> echoes app path
  local arch="$1" bin="$2"
  local app="$WORK/${DISPLAY_NAME}_${arch}.app"
  rm -rf "$app"
  mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
  cp "$bin" "$app/Contents/MacOS/$APP"
  chmod +x "$app/Contents/MacOS/$APP"
  cp build/darwin/Info.plist "$app/Contents/Info.plist"
  cp build/darwin/icons.icns "$app/Contents/Resources/icons.icns"
  printf 'APPL????' > "$app/Contents/PkgInfo"
  plutil -lint "$app/Contents/Info.plist" >/dev/null || die "Info.plist geçersiz"
  sign_target "$app"
  notarize_app "$app"
  echo "$app"
}

package_dmg(){ # app_path goarch
  local app="$1" arch="$2"
  local root="$WORK/dmg_$arch"
  rm -rf "$root"; mkdir -p "$root"
  ditto "$app" "$root/$DISPLAY_NAME.app"
  ln -s /Applications "$root/Applications"
  if [ -f build/darwin/Kurulum.command ]; then
    cp build/darwin/Kurulum.command "$root/Kurulum.command"
    chmod +x "$root/Kurulum.command"
  fi
  local dmg="$OUT/${APP}_darwin_${arch}.dmg"
  hdiutil create -volname "$DISPLAY_NAME" -srcfolder "$root" -ov -format UDZO "$dmg" >/dev/null
  if [ "$IDENTITY" != "-" ]; then
    codesign --force --sign "$IDENTITY" "$dmg" || warn "DMG imzalanamadı"
  fi
  (cd "$OUT" && ditto -c -k --keepParent "$(basename "$app")" "${APP}_darwin_${arch}.app.zip") 2>/dev/null || \
    (cd "$WORK" && zip -qry "$OLDPWD/$OUT/${APP}_darwin_${arch}.app.zip" "$(basename "$app")")
  echo "  -> $dmg"
}

say "macOS (darwin arm64 + amd64)"
for arch in arm64 amd64; do
  BIN="$OUT/${APP}_darwin_${arch}"
  GOOS=darwin GOARCH="$arch" CGO_ENABLED=1 \
    go build -tags production -trimpath -buildvcs=false -ldflags="$LDFLAGS" -o "$BIN"
  echo "  -> $BIN"
  APP_PATH="$(make_app "$arch" "$BIN")"
  package_dmg "$APP_PATH" "$arch"
done

say "Windows (amd64 + arm64)"
for arch in amd64 arm64; do
  if command -v wails3 >/dev/null && [ -f build/windows/icon.ico ]; then
    wails3 generate syso -arch "$arch" -icon build/windows/icon.ico \
      -manifest build/windows/wails.exe.manifest -info build/windows/info.json \
      -out "wails_windows_${arch}.syso" 2>/dev/null || true
  fi
  GOOS=windows GOARCH="$arch" CGO_ENABLED=0 \
    go build -tags production -trimpath -buildvcs=false -ldflags="$LDFLAGS -H windowsgui" \
    -o "$OUT/${APP}_windows_${arch}.exe"
  rm -f ./*.syso
  (cd "$OUT" && zip -qy "${APP}_windows_${arch}.zip" "${APP}_windows_${arch}.exe")
  echo "  -> ${APP}_windows_${arch}.exe / .zip"
done

say "Linux (Docker · GTK4 + WebKitGTK 6.0)"
if command -v docker >/dev/null && docker info >/dev/null 2>&1; then
  for arch in amd64 arm64; do
    IMG="${APP}-linux-${arch}"
    docker build --platform "linux/${arch}" --build-arg GOARCH="$arch" \
      -t "$IMG" -f build/docker/Dockerfile.linux build/docker/ >/dev/null || { warn "$arch imajı yok"; continue; }
    docker run --rm --platform "linux/${arch}" -v "$PWD:/app" -w /app \
      -v "${APP}-gomod-${arch}:/go/pkg/mod" -v "${APP}-gobuild-${arch}:/root/.cache/go-build" \
      -e CGO_ENABLED=1 -e GOOS=linux -e GOARCH="$arch" "$IMG" \
      go build -tags production -trimpath -buildvcs=false -ldflags="$LDFLAGS" \
      -o "$OUT/${APP}_linux_${arch}" || { warn "linux/$arch derlenemedi"; continue; }
    chmod +x "$OUT/${APP}_linux_${arch}"
    tar -czf "$OUT/${APP}_linux_${arch}.tar.gz" -C "$OUT" "${APP}_linux_${arch}"
    if command -v dpkg-deb >/dev/null; then
      D="$WORK/deb_$arch"; rm -rf "$D"
      mkdir -p "$D/DEBIAN" "$D/usr/bin" "$D/usr/share/applications"
      cp "$OUT/${APP}_linux_${arch}" "$D/usr/bin/$APP"
      for s in 16 32 48 64 128 256 512; do
        f="build/linux/icons/hicolor/${s}x${s}/apps/${APP}.png"
        [ -f "$f" ] && install -Dm644 "$f" "$D/usr/share/icons/hicolor/${s}x${s}/apps/${APP}.png"
      done
      [ -f build/linux/ytdlp-studio.desktop ] && \
        install -Dm644 build/linux/ytdlp-studio.desktop "$D/usr/share/applications/${APP}.desktop"
      printf 'Package: %s\nVersion: %s\nArchitecture: %s\nMaintainer: Kadir Niyazi ACAR <%s>\nDepends: libgtk-4-1, libwebkitgtk-6.0-4, libsoup-3.0-0\nDescription: yt-dlp desktop download studio (Bengsoft)\n' \
        "$APP" "$VER" "$arch" "kadirnacar@kadirnacar.com" > "$D/DEBIAN/control"
      dpkg-deb --build "$D" "$OUT/${APP}_linux_${arch}.deb" >/dev/null && echo "  -> ${APP}_linux_${arch}.deb"
      rm -rf "$D"
    fi
  done
else
  warn "Docker yok: Linux paketleri atlandı"
fi

say "Checksums"
(cd "$OUT" && shasum -a 256 * > checksums.txt)
rm -rf "$WORK"
ls -lh "$OUT"

say "Bitti"
echo "release/ klasörünü GitHub Release'e manuel yükleyebilirsiniz."
if [ "$IDENTITY" = "-" ]; then
  echo ""
  echo "NOT: Ad-hoc imza kullanıldı. macOS 26.x'te indirilen uygulama açılmazsa:"
  echo "  • DMG içindeki 'Kurulum.command' dosyasını çalıştırın (quarantine temizler + kurar), veya"
  echo "  • ./fix-macos-app.sh /Applications/${DISPLAY_NAME}.app"
  echo "Kalıcı çözüm (Developer ID):"
  echo "  export CODESIGN_IDENTITY='Developer ID Application: Bengsoft (TEAMID)'"
  echo "  export APPLE_ID='...' APPLE_TEAM_ID='TEAMID' APPLE_APP_PASSWORD='app-specific-password'"
  echo "  ./release.sh"
fi
