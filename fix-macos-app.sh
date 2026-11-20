#!/bin/bash
# ytdlp-studio:fix-macos v1
# Mevcut bir .app'i macOS 15+/26.x Gatekeeper'a uygun hale getirir.
# Kullanım: ./fix-macos-app.sh [/Applications/ytdlp-studio.app]
set -euo pipefail

APP="${1:-/Applications/ytdlp-studio.app}"
if [ ! -d "$APP" ]; then
  echo "HATA: bulunamadı: $APP"
  echo "Kullanım: ./fix-macos-app.sh /Applications/ytdlp-studio.app"
  exit 1
fi

echo "Hedef: $APP"
echo "1/4 · Karantina ve genişletilmiş öznitelikler temizleniyor"
xattr -dr com.apple.quarantine "$APP" 2>/dev/null || true
xattr -cr "$APP" 2>/dev/null || true

echo "2/4 · Bundle yeniden imzalanıyor (ad-hoc)"
codesign --force --deep --sign - "$APP"

echo "3/4 · Doğrulama"
codesign --verify --deep --strict --verbose=2 "$APP" || true
codesign -dv --verbose=2 "$APP" 2>&1 | head -n 12 || true

echo "4/4 · Açılıyor"
open "$APP" || {
  echo ""
  echo "Açılamadıysa: Sistem Ayarları > Gizlilik ve Güvenlik > 'Yine de Aç'."
  echo "Kalıcı çözüm: Developer ID ile imza + notarization (release.sh bunu destekler)."
  exit 1
}
echo "Tamam."
