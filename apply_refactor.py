#!/usr/bin/env python3
"""
apply_refactor.py — ytdlp-studio güvenli refactor scripti

Her patch exact-match doğrulamasıyla uygulanır.
Beklenen içerik bulunmazsa veya birden fazla eşleşme varsa script açık hata verir.
Backup oluşturmaz (Git ile geri alın).
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
FRONTEND = ROOT / "frontend"
CHANGES = []


def report(status, path, message):
    CHANGES.append((status, str(path.relative_to(ROOT)), message))
    icon = {"OK": "✓", "SKIP": "○", "FAIL": "✗"}.get(status, "?")
    print(f"  {icon} {status:4} {path.relative_to(ROOT)} — {message}")


def read(path):
    if not path.exists():
        raise FileNotFoundError(f"Dosya yok: {path}")
    return path.read_text(encoding="utf-8")


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def patch_exact(path, old, new, description):
    """Exact match + post-verify. Hata durumunda exception fırlatır."""
    content = read(path)
    count = content.count(old)
    if count == 0:
        raise RuntimeError(
            f"Beklenen içerik bulunamadı: {path}\n"
            f"Aranan (kısaltıldı): {old[:100]!r}...\n"
            f"Açıklama: {description}"
        )
    if count > 1:
        raise RuntimeError(
            f"Belirsiz eşleşme: {path} içinde {count} kez bulundu\n"
            f"Açıklama: {description}"
        )
    new_content = content.replace(old, new, 1)
    if new not in new_content:
        raise RuntimeError(f"Post-patch doğrulama başarısız: {path}")
    write(path, new_content)
    report("OK", path, description)


def check_structure():
    required = [
        ROOT / "main.go",
        ROOT / "go.mod",
        ROOT / "services",
        ROOT / "internal",
        FRONTEND / "package.json",
        FRONTEND / "tsconfig.json",
    ]
    missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
    if missing:
        print(f"✗ Proje yapısı eksik: {missing}")
        print(f"  Script'in kök dizini: {ROOT}")
        print("  Bu script projenin kök dizininde çalıştırılmalıdır.")
        sys.exit(1)
    print(f"✓ Proje yapısı doğrulandı: {ROOT}")


# ============================================================
# 1. frontend/package.json — name fix
# ============================================================
def fix_package_json():
    path = FRONTEND / "package.json"
    data = json.loads(read(path))
    old = data.get("name", "")
    if old == "react-ts-latest":
        data["name"] = "ytdlp-studio-frontend"
        write(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        report("OK", path, f"name: {old!r} → 'ytdlp-studio-frontend'")
    else:
        report("SKIP", path, f"name zaten {old!r}")


# ============================================================
# 2. frontend/tsconfig.json — trailing comma
# ============================================================
def fix_tsconfig():
    path = FRONTEND / "tsconfig.json"
    patch_exact(
        path,
        '"include": ["src", "bindings"],\n}',
        '"include": ["src", "bindings"]\n}',
        'sondaki virgül kaldırıldı ("include" satırı)',
    )


# ============================================================
# 3. main.go — redundant window size init
# ============================================================
def fix_main_go():
    path = ROOT / "main.go"
    content = read(path)

    old = '''	opts := application.WebviewWindowOptions{
		Title:     "ytdlp-studio",
		Width:     1280,
		Height:    840,
		MinWidth:  960,
		MinHeight: 620,
		URL:       "/",
	}'''
    new = '''	opts := application.WebviewWindowOptions{
		Title: "ytdlp-studio",
		URL:   "/",
	}'''

    if old in content:
        if content.count(old) != 1:
            raise RuntimeError(f"main.go opts bloğu {content.count(old)} kez bulundu")
        write(path, content.replace(old, new, 1))
        report("OK", path, "gereksiz pencere boyutu init temizlendi (tuneWindow tek kaynak)")
        return

    # Regex fallback
    pattern = re.compile(
        r"opts := application\.WebviewWindowOptions\{(?:[^}]|\}(?!\n))\}",
        re.MULTILINE,
    )
    m = pattern.search(content)
    if m and "Width:" in m.group(0) and "tuneWindow" in content:
        write(path, content[:m.start()] + new + content[m.end():])
        report("OK", path, "gereksiz pencere boyutu init temizlendi (regex)")
        return

    raise RuntimeError("main.go opts bloğu beklenen şekilde bulunamadı")


# ============================================================
# 4. types.ts — re-export from bindings
# ============================================================
def unify_types():
    path = FRONTEND / "src" / "types.ts"
    bindings_model = FRONTEND / "bindings" / "ytdlp-studio" / "internal" / "model" / "models.ts"
    bindings_svc = FRONTEND / "bindings" / "ytdlp-studio" / "services" / "models.ts"

    if not bindings_model.exists() or not bindings_svc.exists():
        report("SKIP", path, "bindings models dosyaları yok — unify atlandı")
        return

    old = read(path)
    exported = set(re.findall(r"^export\s+(?:interface|type)\s+(\w+)", old, re.MULTILINE))

    available = set()
    available |= set(re.findall(r"^export\s+(?:interface|type)\s+(\w+)",
                                read(bindings_model), re.MULTILINE))
    available |= set(re.findall(r"^export\s+(?:interface|type)\s+(\w+)",
                                read(bindings_svc), re.MULTILINE))
    local = {"Tab"}
    uncovered = exported - available - local
    if uncovered:
        raise RuntimeError(
            f"types.ts içinde binding'lerde olmayan tipler var: {sorted(uncovered)}\n"
            f"Bunlar re-export edilemez. Güvenli değil, atlandı."
        )

    new_content = '''// ytdlp-studio:types v4 — tek kaynak: Wails bindings
// Elle tip tanımı YOKTUR. Drift imkânsızdır.

export type {
  AppSettings,
  DownloadOptions,
  MediaEntry,
  MediaInfo,
  ParsedURL,
} from "../bindings/ytdlp-studio/internal/model/models";

export type {
  BatchInfo,
  BatchProgress,
  DepStatus,
  LogLine,
  SubtitleInfo,
  SubtitleTrack,
  TaskProgress,
} from "../bindings/ytdlp-studio/services/models";

export type Tab = "analyze" | "queue" | "settings" | "logs" | "about";
'''
    write(path, new_content)
    report("OK", path, f"re-export'a dönüştürüldü ({len(exported)} tip korundu)")


# ============================================================
# 5. App.tsx — startup hydration + Tab cast
# ============================================================
def fix_app_tsx():
    path = FRONTEND / "src" / "App.tsx"

    patch_exact(
        path,
        'import { DepsService, SettingsService } from "./api";',
        'import { DepsService, DownloadService, SettingsService } from "./api";',
        "DownloadService import eklendi",
    )

    patch_exact(
        path,
        'import type { BatchProgress, DepStatus, LogLine, TaskProgress } from "./types";',
        'import type { BatchProgress, DepStatus, LogLine, Tab, TaskProgress } from "./types";',
        "Tab tipi import edildi",
    )

    old_effect = '''  useEffect(() => {
    SettingsService.Load().then((o) => set({ options: o })).catch(() => undefined);
    SettingsService.LoadApp().then((a) => { set({ app: a, tab: a.defaultTab as any }); setLogLimit(a.maxLogLines); }).catch(() => undefined);
    DepsService.CheckDeps().then((d) => set({ deps: d })).catch(() => undefined);
  }, [set, setLogLimit]);'''

    new_effect = '''  useEffect(() => {
    SettingsService.Load().then((o) => set({ options: o })).catch(() => undefined);
    SettingsService.LoadApp()
      .then((a) => {
        set({ app: a, tab: a.defaultTab as Tab });
        setLogLimit(a.maxLogLines);
      })
      .catch(() => undefined);
    DepsService.CheckDeps().then((d) => set({ deps: d })).catch(() => undefined);

    // Startup hydration: event'ler kaçırılmış olsa da UI backend ile eşitlenir.
    DownloadService.Snapshot()
      .then((tasks) => { if (tasks) tasks.forEach((t) => upsert(t)); })
      .catch(() => undefined);
    DownloadService.Batches()
      .then((batches) => { if (batches) batches.forEach((b) => upsertBatch(b)); })
      .catch(() => undefined);
  }, [set, setLogLimit, upsert, upsertBatch]);'''

    patch_exact(path, old_effect, new_effect,
                "startup Snapshot/Batches eklendi, 'as any' → 'as Tab' düzeltildi")


# ============================================================
# 6. .gitignore
# ============================================================
def ensure_gitignore():
    path = ROOT / ".gitignore"
    needed = [
        "/bin/", "/dist/", "/release/", "/build/_release/",
        "frontend/node_modules/", "frontend/dist/",
        "*.syso", ".DS_Store",
    ]
    if path.exists():
        content = read(path)
        missing = [p for p in needed if p not in content]
        if missing:
            write(path, content.rstrip() + "\n\n# ytdlp-studio additions\n"
                  + "\n".join(missing) + "\n")
            report("OK", path, f"{len(missing)} eksik pattern eklendi")
        else:
            report("SKIP", path, "zaten tam")
    else:
        write(path, """# Build
/bin/
/dist/
/release/
/build/_release/

# Node
frontend/node_modules/
frontend/dist/

# Wails
*.syso

# OS
.DS_Store
Thumbs.db

# Go
*.test
*.out
""")
        report("OK", path, "oluşturuldu")


# ============================================================
# 7. LICENSE (MIT)
# ============================================================
def ensure_license():
    path = ROOT / "LICENSE"
    if path.exists():
        report("SKIP", path, "zaten var")
        return
    write(path, """MIT License

Copyright (c) 2026 Kadir Niyazi ACAR

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
""")
    report("OK", path, "MIT lisansı oluşturuldu")


# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 62)
    print("apply_refactor.py — ytdlp-studio güvenli patch")
    print("=" * 62)
    check_structure()

    steps = [
        ("package.json name",   fix_package_json),
        ("tsconfig virgül",     fix_tsconfig),
        ("main.go opts",        fix_main_go),
        ("types.ts unify",      unify_types),
        ("App.tsx startup",     fix_app_tsx),
        (".gitignore",          ensure_gitignore),
        ("LICENSE",             ensure_license),
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
        print(f"\n{len(failed)} adım başarısız — çıktıyı inceleyin:")
        for label, err in failed:
            print(f"  ✗ {label}: {err.splitlines()[0]}")
        sys.exit(1)

    print(f"\n✓ Tüm patch işlemleri tamamlandı ({len(CHANGES)} adım).")


if __name__ == "__main__":
    main()