#!/usr/bin/env python3
"""
ytdlp-studio · Yeni release etiketi oluşturucu (Bengsoft)  [new-release v2]

Kullanım:
  python3 scripts/new_release.py patch
  python3 scripts/new_release.py minor --message "Altyazı modu"
  python3 scripts/new_release.py --version 1.4.0 --no-push
  python3 scripts/new_release.py major --skip-checks --dry-run

Neden `go build ./...` KULLANMIYORUZ:
  Wails, build/ios ve build/android altında `package main` ama `func main()`
  olmayan mobil stub paketleri üretir. `go build ./...` bu paketleri derlemeye
  çalışıp "function main is undeclared" ile KIRILIR. Doğru doğrulama `wails3 build`
  (veya kök paket için `go build -tags production .`) ve `go test ./internal/... ./services/...`
  şeklindedir. macOS linker minOS uyarıları MACOSX_DEPLOYMENT_TARGET + CGO_*FLAGS +
  -extldflags ile susturulur.

Yaptıkları:
  1) git durumu/branch kontrolü
  2) wails3 build (fallback: go build -tags production .) + dar kapsamlı go test + frontend build
  3) sürüm alanlarını günceller (Info.plist, info.json, brand.ts, package.json, release.sh, workflow)
  4) commit + annotated tag (vX.Y.Z) + push
  5) opsiyonel: gh ile workflow_dispatch tetikleme
Markdown dosyası üretmez, backup almaz.
"""

import argparse
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

MARKER = "new-release v2"


def root():
    c = Path(__file__).resolve().parent
    for p in [c] + list(c.parents):
        if (p / "go.mod").exists() and (p / "Taskfile.yml").exists():
            return p
    raise SystemExit("ERROR: proje kökü bulunamadı")


ROOT = root()


def git(*args, check=True, capture=True):
    p = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=capture)
    if check and p.returncode != 0:
        raise SystemExit(f"ERROR: git {' '.join(args)}\n{p.stderr or p.stdout}")
    return (p.stdout or "").strip()


def build_env():
    """macOS linker minOS uyarılarını gideren ortam."""
    e = dict(os.environ)
    if sys.platform == "darwin":
        minos = e.get("MACOSX_DEPLOYMENT_TARGET", "13.0")
        e["MACOSX_DEPLOYMENT_TARGET"] = minos
        e["CGO_CFLAGS"] = (e.get("CGO_CFLAGS", "") + f" -mmacosx-version-min={minos}").strip()
        e["CGO_LDFLAGS"] = (e.get("CGO_LDFLAGS", "") + f" -mmacosx-version-min={minos}").strip()
        e["GOFLAGS"] = (e.get("GOFLAGS", "") + f" -ldflags=-extldflags=-mmacosx-version-min={minos}").strip()
    return e


def sh(cmd, cwd=None, check=True, env=None):
    print("$ " + " ".join(map(str, cmd)))
    p = subprocess.run(list(map(str, cmd)), cwd=str(cwd or ROOT), env=env or build_env())
    if check and p.returncode != 0:
        raise SystemExit(f"ERROR: komut başarısız: {' '.join(map(str, cmd))}")
    return p.returncode


def current_version():
    pl = ROOT / "build" / "darwin" / "Info.plist"
    if pl.exists():
        try:
            v = plistlib.loads(pl.read_bytes()).get("CFBundleShortVersionString")
            if v:
                return str(v)
        except Exception:
            pass
    brand = ROOT / "frontend" / "src" / "lib" / "brand.ts"
    if brand.exists():
        m = re.search(r'version:\s*"([0-9]+\.[0-9]+\.[0-9]+)"', brand.read_text(encoding="utf-8"))
        if m:
            return m.group(1)
    return "0.0.0"


def bump(v, kind):
    parts = v.split(".")
    while len(parts) < 3:
        parts.append("0")
    try:
        major, minor, patch = (int(x) for x in parts[:3])
    except ValueError:
        raise SystemExit(f"ERROR: sürüm çözümlenemedi: {v}")
    if kind == "major":
        return f"{major + 1}.0.0"
    if kind == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def run_checks():
    print("\n== Kontroller (wails3 build + dar kapsamlı test) ==")
    env = build_env()

    # 1) Frontend production build (embed için zorunlu)
    fe = ROOT / "frontend"
    if not (fe / "node_modules").exists():
        sh(["npm", "install", "--no-audit", "--no-fund"], cwd=fe, env=env)
    sh(["npm", "run", "build"], cwd=fe, env=env)

    # 2) Uygulama derlemesi: wails3 build tercih; yoksa kök paket
    if shutil.which("wails3"):
        sh(["wails3", "build"], env=env)
    else:
        print("NOT: wails3 CLI yok; kök paket tek başına derleniyor (build/ios, build/android atlanır)")
        sh(["go", "build", "-tags", "production", "."], env=env)

    # 3) Testler: SADECE kendi paketlerimiz (build/... hariç -> main yok)
    sh(["go", "test", "./internal/...", "./services/..."], env=env, check=False)

    # 4) go vet de aynı kapsamla
    sh(["go", "vet", "./internal/...", "./services/..."], env=env, check=False)


def set_text(path, pattern, repl, label, required=False):
    p = ROOT / path
    if not p.exists():
        if required:
            raise SystemExit(f"ERROR: {path} yok")
        print(f"SKIP    : {path} (yok)")
        return
    c = p.read_text(encoding="utf-8")
    new = re.sub(pattern, repl, c, count=1)
    if new == c:
        print(f"SKIP    : {path} ({label} kalıbı bulunamadı)")
        return
    p.write_text(new, encoding="utf-8")
    print(f"UPDATED : {path} ({label})")


def write_versions(ver):
    print("\n== Sürüm alanları ==")
    pl = ROOT / "build" / "darwin" / "Info.plist"
    if pl.exists():
        data = plistlib.loads(pl.read_bytes())
        data["CFBundleShortVersionString"] = ver
        try:
            data["CFBundleVersion"] = str(int(str(data.get("CFBundleVersion", "0"))) + 1)
        except ValueError:
            data["CFBundleVersion"] = "1"
        data["CFBundleGetInfoString"] = f"ytdlp-studio {ver} · Bengsoft"
        pl.write_bytes(plistlib.dumps(data))
        print(f"UPDATED : build/darwin/Info.plist ({ver}, build {data['CFBundleVersion']})")

    ij = ROOT / "build" / "windows" / "info.json"
    if ij.exists():
        j = json.loads(ij.read_text(encoding="utf-8"))
        sfi = j.setdefault("StringFileInfo", {})
        sfi["FileVersion"] = ver
        sfi["ProductVersion"] = ver
        ffi = j.get("FixedFileInfo")
        if isinstance(ffi, dict):
            nums = [int(x) for x in ver.split(".")] + [0]
            for key in ("FileVersion", "ProductVersion"):
                if isinstance(ffi.get(key), dict):
                    ffi[key] = {"Major": nums[0], "Minor": nums[1], "Patch": nums[2], "Build": 0}
        ij.write_text(json.dumps(j, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"UPDATED : build/windows/info.json ({ver})")

    set_text("frontend/src/lib/brand.ts", r'version:\s*"[0-9]+\.[0-9]+\.[0-9]+"',
             f'version: "{ver}"', "brand.ts")
    set_text("frontend/package.json", r'"version":\s*"[^"]+"',
             f'"version": "{ver}"', "package.json")
    set_text("release.sh", r'VER="\$\{VERSION:-[0-9.]*\}"',
             f'VER="${{VERSION:-{ver}}}"', "release.sh fallback")
    set_text(".github/workflows/release.yml", r"Version: [0-9]+\.[0-9]+\.[0-9]+",
             f"Version: {ver}", "workflow deb version")


def write_versions_preview(ver):
    print("Güncellenecek alanlar:")
    for p in ("build/darwin/Info.plist", "build/windows/info.json",
              "frontend/src/lib/brand.ts", "frontend/package.json",
              "release.sh", ".github/workflows/release.yml"):
        print(f"  - {p} -> {ver}")


def main():
    ap = argparse.ArgumentParser(description="ytdlp-studio release tag oluşturucu")
    ap.add_argument("bump", nargs="?", choices=["patch", "minor", "major"], default="patch")
    ap.add_argument("--version", dest="explicit", help="Açık sürüm (örn. 1.4.0)")
    ap.add_argument("--message", "-m", default="", help="Tag açıklaması")
    ap.add_argument("--no-push", action="store_true", help="Push yapma")
    ap.add_argument("--skip-checks", action="store_true", help="build/test atla")
    ap.add_argument("--allow-dirty", action="store_true", help="kirli working tree'ye izin ver")
    ap.add_argument("--dry-run", action="store_true", help="hiçbir şey yazma/commit yapma")
    ap.add_argument("--dispatch", action="store_true", help="gh ile workflow_dispatch tetikle")
    args = ap.parse_args()

    cur = current_version()
    ver = args.explicit or bump(cur, args.bump)
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", ver):
        raise SystemExit(f"ERROR: geçersiz sürüm: {ver}")
    tag = f"v{ver}"

    print(f"Proje: {ROOT}")
    print(f"Sürüm: {cur} -> {ver}  (tag {tag})")

    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    print(f"Branch: {branch}")
    dirty = git("status", "--porcelain")
    if dirty and not args.allow_dirty:
        raise SystemExit("ERROR: working tree kirli. Commit edin veya --allow-dirty kullanın.\n" + dirty)
    if git("tag", "-l", tag):
        raise SystemExit(f"ERROR: {tag} etiketi zaten var.")

    if not args.skip_checks and not args.dry_run:
        run_checks()

    if args.dry_run:
        print("\nDRY-RUN: dosya/commit/tag işlemi yapılmadı.")
        write_versions_preview(ver)
        return

    write_versions(ver)

    print("\n== Git ==")
    sh(["git", "add", "-A"])
    msg = f"chore(release): {tag}"
    if args.message:
        msg += f"\n\n{args.message}"
    if git("diff", "--cached", "--name-only"):
        sh(["git", "commit", "-m", msg])
    else:
        print("NOT: sürüm dosyalarında değişiklik yok; sadece tag oluşturulacak.")
    tag_msg = f"ytdlp-studio {ver} · Bengsoft"
    if args.message:
        tag_msg += f"\n\n{args.message}"
    sh(["git", "tag", "-a", tag, "-m", tag_msg])

    if args.no_push:
        print(f"\nPush atlandı. Elle: git push origin {branch} && git push origin {tag}")
    else:
        sh(["git", "push", "origin", branch])
        sh(["git", "push", "origin", tag])
        print(f"\nTag pushed: {tag} → GitHub Actions release workflow tetiklenir.")

    if args.dispatch:
        if shutil.which("gh"):
            sh(["gh", "workflow", "run", "release.yml", "-f", f"tag={tag}"], check=False)
        else:
            print("NOT: gh CLI yok, workflow_dispatch tetiklenmedi.")

    print("\n== ÖZET ==")
    print(f"Sürüm : {ver}")
    print(f"Tag   : {tag}")
    print("Sonraki: GitHub > Releases sayfasında varlıkları kontrol edin.")
    print("Yerel paketleme için: ./release.sh")


if __name__ == "__main__":
    main()
