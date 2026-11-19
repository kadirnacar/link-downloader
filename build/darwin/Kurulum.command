#!/bin/bash
# Bengsoft · ytdlp-studio kurulum yardımcısı
# Quarantine temizler, /Applications'a kurar ve uygulamayı açar.
set -euo pipefail

APP="ytdlp-studio.app"
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/$APP"

echo "──────────────────────────────────────────────"
echo " ytdlp-studio · Bengsoft"
echo " Kadir Niyazi AÇAR · kadirnacar@kadirnacar.com"
echo "──────────────────────────────────────────────"

if [ ! -d "$SRC" ]; then
  echo "HATA: $SRC bulunamadı. Bu dosyayı DMG içindeki .app ile aynı klasörden çalıştırın."
  read -r -p "Kapatmak için Enter…" _
  exit 1
fi

DST="/Applications/$APP"
if ! mkdir -p /Applications 2>/dev/null || [ ! -w /Applications ]; then
  mkdir -p "$HOME/Applications"
  DST="$HOME/Applications/$APP"
fi

echo "Kuruluyor: $DST"
rm -rf "$DST" 2>/dev/null || true
cp -R "$SRC" "$DST"

echo "Karantina kaldırılıyor…"
xattr -dr com.apple.quarantine "$DST" 2>/dev/null || true
xattr -cr "$DST" 2>/dev/null || true

echo "Yerel (ad-hoc) imza uygulanıyor…"
codesign --force --deep --sign - "$DST" 2>/dev/null || true
codesign --verify --deep --strict "$DST" 2>/dev/null && echo "İmza doğrulandı." || echo "Uyarı: imza doğrulanamadı (devam ediliyor)."

echo "Açılıyor…"
open "$DST" || true
echo ""
echo "Tamamlandı. Sorun olursa: Sistem Ayarları > Gizlilik ve Güvenlik > 'Yine de Aç'."
read -r -p "Kapatmak için Enter…" _
