#!/bin/bash
# ytdlp-studio:release-sh v3
# macOS host · os_arch paketleri + doğru .app imzalama/notarization
# KRİTİK: tüm teşhis çıktısı stderr'e gider; make_app global APP_PATH set eder.
set -euo pipefail

APP="ytdlp-studio"
DISPLAY_NAME="ytdlp-studio"
OUT="release"
WORK="build/_release"
IDENTITY="${CODESIGN_IDENTITY:--}"
TARGETS="${TARGETS:-darwin windows linux}"
MIN_MACOS="${MACOSX_DEPLOYMENT_TARGET:-13.0}"

export MACOSX_DEPLOYMENT_TARGET="$MIN_MACOS"
export CGO_CFLAGS="${CGO_CFLAGS:-} -mmacosx-version-min=$MIN_MACOS"
export CGO_LDFLAGS="${CGO_LDFLAGS:-} -mmacosx-version-min=$MIN_MACOS"

VER="${VERSION:-1.0.1}"
if [ -z "$VER" ] && [ -x /usr/libexec/PlistBuddy ] && [ -f build/darwin/Info.plist ]; then
  VER="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' build/darwin/Info.plist 2>/dev/null || true)"
fi
VER="${VER:-1.0.0}"
LDFLAGS="-w -s"

say(){ printf "\n\033[1;36m== %s\033[0m\n" "$1" >&2; }
warn(){ printf "\033[1;33m! %s\033[0m\n" "$1" >&2; }
die(){ printf "\033[1;31mx %s\033[0m\n" "$1" >&2; exit 1; }
info(){ printf "  %s\n" "$1" >&2; }

command -v go >/dev/null || die "go yok"
command -v npm >/dev/null || die "npm yok"
[ -f build/darwin/Info.plist ] || die "build/darwin/Info.plist yok"
[ -f build/darwin/icons.icns ] || die "build/darwin/icons.icns yok"

rm -rf "$OUT" "$WORK"; mkdir -p "$OUT" "$WORK"
OUT_ABS="$(cd "$OUT" && pwd)"
WORK_ABS="$(cd "$WORK" && pwd)"
say "Sürüm $VER · hedefler: $TARGETS · minOS $MIN_MACOS"

say "Frontend (production)"
(cd frontend && npm install --no-audit --no-fund >&2 && npm run build >&2)
[ -f frontend/dist/index.html ] || die "frontend/dist yok"

if command -v wails3 >/dev/null; then
  say "Bindings"
  wails3 generate bindings -clean=true -ts -i >&2 || warn "bindings üretilemedi"
fi

APP_PATH=""

sign_target(){
  local target="$1"
  xattr -cr "$target" >&2 2>/dev/null || true
  if [ "$IDENTITY" = "-" ]; then
    codesign --force --deep --sign - "$target" >&2
  else
    codesign --force --deep --options runtime --timestamp --sign "$IDENTITY" "$target" >&2
  fi
  codesign --verify --deep --strict "$target" >&2 || die "imza doğrulanamadı: $target"
}

notarize_app(){
  local app="$1"
  if [ "$IDENTITY" = "-" ]; then
    warn "Ad-hoc imza: notarization yok. DMG içindeki 'Kurulum.command' quarantine'i temizler."
    return 0
  fi
  if [ -z "${APPLE_ID:-}" ] || [ -z "${APPLE_TEAM_ID:-}" ] || [ -z "${APPLE_APP_PASSWORD:-}" ]; then
    warn "APPLE_ID/APPLE_TEAM_ID/APPLE_APP_PASSWORD yok: notarization atlandı"
    return 0
  fi
  say "Notarization: $(basename "$app")"
  local zip="$WORK_ABS/notarize.zip"
  rm -f "$zip"
  ditto -c -k --keepParent "$app" "$zip"
  xcrun notarytool submit "$zip" --apple-id "$APPLE_ID" --team-id "$APPLE_TEAM_ID" \
    --password "$APPLE_APP_PASSWORD" --wait >&2 || die "notarization başarısız"
  xcrun stapler staple "$app" >&2 || warn "staple başarısız"
  xcrun stapler validate "$app" >&2 || true
}

# APP_PATH globalini set eder; stdout'a HİÇBİR ŞEY yazmaz.
make_app(){
  local arch="$1" bin="$2"
  local app="$WORK_ABS/${DISPLAY_NAME}_${arch}.app"
  rm -rf "$app"
  mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
  cp "$bin" "$app/Contents/MacOS/$APP"
  chmod +x "$app/Contents/MacOS/$APP"
  cp build/darwin/Info.plist "$app/Contents/Info.plist"
  cp build/darwin/icons.icns "$app/Contents/Resources/icons.icns"
  printf 'APPL????' > "$app/Contents/PkgInfo"
  plutil -lint "$app/Contents/Info.plist" >&2 || die "Info.plist geçersiz"
  sign_target "$app"
  notarize_app "$app"
  APP_PATH="$app"
}

package_dmg(){
  local app="$1" arch="$2"
  [ -d "$app" ] || die "app bundle yok: $app"
  local root="$WORK_ABS/dmg_$arch"
  rm -rf "$root"; mkdir -p "$root"
  ditto "$app" "$root/$DISPLAY_NAME.app"
  ln -s /Applications "$root/Applications"
  if [ -f build/darwin/Kurulum.command ]; then
    cp build/darwin/Kurulum.command "$root/Kurulum.command"
    chmod +x "$root/Kurulum.command"
  fi
  local dmg="$OUT_ABS/${APP}_darwin_${arch}.dmg"
  hdiutil create -volname "$DISPLAY_NAME" -srcfolder "$root" -ov -format UDZO "$dmg" >&2 >/dev/null
  if [ "$IDENTITY" != "-" ]; then
    codesign --force --sign "$IDENTITY" "$dmg" >&2 || warn "DMG imzalanamadı"
  fi
  (cd "$WORK_ABS" && ditto -c -k --keepParent "$(basename "$app")" "$OUT_ABS/${APP}_darwin_${arch}.app.zip")
  info "-> ${APP}_darwin_${arch}.dmg / .app.zip"
}

case " $TARGETS " in *" darwin "*)
  command -v codesign >/dev/null || die "codesign yok (Xcode CLT)"
  say "macOS (darwin arm64 + amd64)"
  for arch in arm64 amd64; do
    BIN="$OUT_ABS/${APP}_darwin_${arch}"
    GOOS=darwin GOARCH="$arch" CGO_ENABLED=1 \
      go build -tags production -trimpath -buildvcs=false -ldflags="$LDFLAGS" -o "$BIN"
    info "-> $BIN"
    make_app "$arch" "$BIN"
    package_dmg "$APP_PATH" "$arch"
  done
;; esac

case " $TARGETS " in *" windows "*)
  say "Windows (amd64 + arm64)"
  for arch in amd64 arm64; do
    if command -v wails3 >/dev/null && [ -f build/windows/icon.ico ]; then
      wails3 generate syso -arch "$arch" -icon build/windows/icon.ico \
        -manifest build/windows/wails.exe.manifest -info build/windows/info.json \
        -out "wails_windows_${arch}.syso" >&2 2>/dev/null || true
    fi
    GOOS=windows GOARCH="$arch" CGO_ENABLED=0 \
      go build -tags production -trimpath -buildvcs=false -ldflags="$LDFLAGS -H windowsgui" \
      -o "$OUT_ABS/${APP}_windows_${arch}.exe"
    rm -f ./*.syso
    (cd "$OUT_ABS" && zip -qy "${APP}_windows_${arch}.zip" "${APP}_windows_${arch}.exe")
    info "-> ${APP}_windows_${arch}.exe / .zip"
  done
;; esac

case " $TARGETS " in *" linux "*)
  say "Linux (Docker · GTK4 + WebKitGTK 6.0)"
  if command -v docker >/dev/null && docker info >/dev/null 2>&1; then
    for arch in amd64 arm64; do
      IMG="${APP}-linux-${arch}"
      if ! docker build --platform "linux/${arch}" --build-arg GOARCH="$arch" \
        -t "$IMG" -f build/docker/Dockerfile.linux build/docker/ >&2; then
        warn "linux/$arch imajı kurulamadı"; continue
      fi
      if ! docker run --rm --platform "linux/${arch}" -v "$PWD:/app" -w /app \
        -v "${APP}-gomod-${arch}:/go/pkg/mod" -v "${APP}-gobuild-${arch}:/root/.cache/go-build" \
        -e CGO_ENABLED=1 -e GOOS=linux -e GOARCH="$arch" "$IMG" \
        go build -tags production -trimpath -buildvcs=false -ldflags="$LDFLAGS" \
        -o "$OUT/${APP}_linux_${arch}" >&2; then
        warn "linux/$arch derlenemedi"; continue
      fi
      chmod +x "$OUT_ABS/${APP}_linux_${arch}"
      tar -czf "$OUT_ABS/${APP}_linux_${arch}.tar.gz" -C "$OUT_ABS" "${APP}_linux_${arch}"
      if command -v dpkg-deb >/dev/null; then
        D="$WORK_ABS/deb_$arch"; rm -rf "$D"
        mkdir -p "$D/DEBIAN" "$D/usr/bin" "$D/usr/share/applications"
        cp "$OUT_ABS/${APP}_linux_${arch}" "$D/usr/bin/$APP"
        for s in 16 32 48 64 128 256 512; do
          f="build/linux/icons/hicolor/${s}x${s}/apps/${APP}.png"
          [ -f "$f" ] && install -Dm644 "$f" "$D/usr/share/icons/hicolor/${s}x${s}/apps/${APP}.png"
        done
        [ -f build/linux/ytdlp-studio.desktop ] && \
          install -Dm644 build/linux/ytdlp-studio.desktop "$D/usr/share/applications/${APP}.desktop"
        printf 'Package: %s\nVersion: %s\nArchitecture: %s\nMaintainer: Kadir Niyazi ACAR <kadirnacar@kadirnacar.com>\nDepends: libgtk-4-1, libwebkitgtk-6.0-4, libsoup-3.0-0\nDescription: yt-dlp desktop download studio (Bengsoft)\n' \
          "$APP" "$VER" "$arch" > "$D/DEBIAN/control"
        dpkg-deb --build "$D" "$OUT_ABS/${APP}_linux_${arch}.deb" >&2 >/dev/null && info "-> ${APP}_linux_${arch}.deb"
        rm -rf "$D"
      fi
      info "-> ${APP}_linux_${arch} / .tar.gz"
    done
  else
    warn "Docker yok: Linux paketleri atlandı"
  fi
;; esac

say "Checksums"
(cd "$OUT_ABS" && shasum -a 256 * > checksums.txt)
rm -rf "$WORK_ABS"
ls -lh "$OUT_ABS" >&2

say "Bitti"
info "release/ klasörünü GitHub Release'e yükleyebilirsiniz."
if [ "$IDENTITY" = "-" ]; then
  info "Ad-hoc imza: macOS 26.x'te açılmazsa DMG içindeki 'Kurulum.command' veya ./fix-macos-app.sh"
  info "Kalıcı: CODESIGN_IDENTITY + APPLE_ID/APPLE_TEAM_ID/APPLE_APP_PASSWORD ile ./release.sh"
fi
