#!/usr/bin/env python3
"""
apply_round2.py — Round 2 patch
  - export.py: Dockerfile* glob + repo hygiene config dosyaları
  - main.go:   EnsureDeps / UpdateYtDlp hata yolları

Ön koşul: apply_refactor.py çalışmış olmalı (main.go opts bloğu temizlenmiş).
Idempotent: yeniden çalıştırılabilir; değişiklik zaten varsa SKIP.
Backup YOK — değişiklikleri Git ile geri alın.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
CHANGES = []


def report(status, path, message):
    CHANGES.append((status, str(path.relative_to(ROOT)), message))
    icon = {"OK": "✓", "SKIP": "○", "FAIL": "✗"}.get(status, "?")
    print(f"  {icon} {status:4} {path.relative_to(ROOT)} — {message}")


def read(path):
    if not path.exists():
        raise FileNotFoundError(f"Yok: {path}")
    return path.read_text(encoding="utf-8")


def write(path, content):
    path.write_text(content, encoding="utf-8")


def patch_exact(path, old, new, description, idempotent_marker=None):
    content = read(path)
    if idempotent_marker and idempotent_marker in content:
        report("SKIP", path, f"zaten uygulanmış ({description})")
        return False
    count = content.count(old)
    if count == 0:
        raise RuntimeError(f"Beklenen içerik yok: {path}\n  {description}\n"
                           f"  Aranan (kısaltıldı): {old[:120]!r}")
    if count > 1:
        raise RuntimeError(f"Belirsiz ({count} eşleşme): {path}\n  {description}")
    new_content = content.replace(old, new, 1)
    if new not in new_content:
        raise RuntimeError(f"Post-patch doğrulama başarısız: {path}")
    write(path, new_content)
    report("OK", path, description)
    return True


# ============================================================
# export.py — Dockerfile* + config uzantıları
# ============================================================
def fix_export_py():
    path = ROOT / "export.py"
    old = (
        '    "*.html",\n'
        '    "Dockerfile"\n'
    )
    new = (
        '    "*.html",\n'
        '    "Dockerfile*",       # Dockerfile, Dockerfile.linux, Dockerfile.arm64\n'
        '    ".gitignore",\n'
        '    ".gitattributes",\n'
        '    "*.desktop",\n'
        '    "*.manifest",\n'
        '    "*.command",\n'
    )
    patch_exact(path, old, new,
                "Dockerfile* glob + .gitignore/.gitattributes/.desktop/.manifest/.command",
                idempotent_marker='"Dockerfile*"')


# ============================================================
# main.go — goroutine hata yolları
# ============================================================
def fix_main_errors():
    path = ROOT / "main.go"

    # --- EnsureDeps ---
    old_deps = (
        '\tif appCfg.CheckDepsOnStart {\n'
        '\t\tgo deps.EnsureDeps()\n'
        '\t}\n'
    )
    new_deps = (
        '\tif appCfg.CheckDepsOnStart {\n'
        '\t\tgo func() {\n'
        '\t\t\tif _, err := deps.EnsureDeps(); err != nil {\n'
        '\t\t\t\tlog.Printf("dependency check failed: %v", err)\n'
        '\t\t\t}\n'
        '\t\t}()\n'
        '\t}\n'
    )

    content = read(path)
    if new_deps in content:
        report("SKIP", path, "EnsureDeps hata yolu zaten ekli")
    elif old_deps in content:
        patch_exact(path, old_deps, new_deps, "EnsureDeps hata yakalama")
    else:
        # space-indent fallback
        old_sp = old_deps.replace("\t", "    ")
        if old_sp in content:
            patch_exact(path, old_sp, new_deps.replace("\t", "    "),
                        "EnsureDeps hata yakalama (space indent)")
        else:
            raise RuntimeError(
                "EnsureDeps bloğu main.go'da bulunamadı. "
                "apply_refactor.py sonrası main.go değişmiş olabilir; "
                "elle kontrol edin."
            )

    # --- UpdateYtDlp ---
    old_upd = (
        '\tif appCfg.YtDlpAutoUpdate {\n'
        '\t\tgo func() { _, _ = deps.UpdateYtDlp(appCfg.YtDlpChannel) }()\n'
        '\t}\n'
    )
    new_upd = (
        '\tif appCfg.YtDlpAutoUpdate {\n'
        '\t\tgo func() {\n'
        '\t\t\tif _, err := deps.UpdateYtDlp(appCfg.YtDlpChannel); err != nil {\n'
        '\t\t\t\tlog.Printf("yt-dlp auto-update failed (channel=%s): %v", appCfg.YtDlpChannel, err)\n'
        '\t\t\t}\n'
        '\t\t}()\n'
        '\t}\n'
    )

    content = read(path)  # re-read after first patch
    if new_upd in content:
        report("SKIP", path, "UpdateYtDlp hata yolu zaten ekli")
    elif old_upd in content:
        patch_exact(path, old_upd, new_upd, "UpdateYtDlp hata yakalama")
    else:
        old_sp = old_upd.replace("\t", "    ")
        if old_sp in content:
            patch_exact(path, old_sp, new_upd.replace("\t", "    "),
                        "UpdateYtDlp hata yakalama (space indent)")
        else:
            raise RuntimeError(
                "UpdateYtDlp bloğu main.go'da bulunamadı. "
                "Orijinalde '_, _ = deps.UpdateYtDlp(...)' satırı bekleniyordu."
            )


def main():
    print("=" * 62)
    print("apply_round2.py")
    print("=" * 62)

    # Sanity: proje kökünde miyiz?
    if not (ROOT / "main.go").exists() or not (ROOT / "export.py").exists():
        print(f"✗ Proje kökünde değiliz: {ROOT}")
        print("  main.go ve export.py bu dizinde olmalı.")
        sys.exit(1)
    print(f"✓ Proje kökü: {ROOT}")

    steps = [
        ("export.py — filtre düzeltmesi", fix_export_py),
        ("main.go — hata yakalama", fix_main_errors),
    ]
    failed = []
    for label, fn in steps:
        print(f"\n▶ {label}")
        try:
            fn()
        except Exception as e:
            print(f"  ✗ FAIL: {e}")
            failed.append((label, str(e)))

    print("\n" + "=" * 62)
    print("ÖZET")
    print("=" * 62)
    for status, path, msg in CHANGES:
        icon = {"OK": "✓", "SKIP": "○", "FAIL": "✗"}.get(status, "?")
        print(f"  {icon} {status:4} {path} — {msg}")

    if failed:
        print(f"\n{len(failed)} adım başarısız.")
        sys.exit(1)

    print(f"\n✓ Round 2 tamamlandı ({len(CHANGES)} adım).")


if __name__ == "__main__":
    main()