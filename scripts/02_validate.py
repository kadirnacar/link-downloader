#!/usr/bin/env python3
# 02_validate.py — bindings üretimi, build/test doğrulaması ve final rapor.
import json
import os
import re
import sys
from pathlib import Path

from _common import (Report, base_parser, die, ensure_tool, ensure_wails3,
                     find_root, go_env, guard_main, read, run, write_verified)

COMMIT_MSG = """feat: add yt-dlp URL analysis, preview and rule-based download pipeline

- add AnalyzeService: URL parsing (video/playlist/shorts/mix, v+list ambiguity) and flat-playlist preview with thumbnails
- add DownloadService: worker queue, progress events, cancel/retry, native folder picker and Finder reveal
- add DownloadOptions model with validation and yt-dlp flag builder (audio/video mode, quality, embeds, rate limit, cookies)
- add DepsService (yt-dlp/ffmpeg/ffprobe/deno-bun detection + managed install + update) and SettingsService persistence
- replace Wails template UI with React analyze/queue screens (zustand stores, typed progress event feed)
- wire all services and typed events in main.go; rename module changeme -> ytdlp-studio; add go-ytdlp and zustand deps
- remove template greet service and unused CSS/assets; add ParseURL and options validation unit tests
"""


def heal_api_import(root, report):
    api = root / "frontend" / "src" / "api.ts"
    text = read(api)
    m = re.search(r'from "(\.\./bindings/[^"]+)"', text)
    if not m:
        die("ERROR:\napi.ts içinde binding import satırı bulunamadı. Patch uygulanmadı.")
    current = m.group(1)
    target = (api.parent / current).resolve()
    if (target / "index.ts").is_file():
        report.skipped.append("frontend/src/api.ts (binding yolu zaten doğru)")
        return
    hits = sorted((root / "frontend" / "bindings").rglob("services/index.ts"))
    if not hits:
        die("ERROR:\nBinding üretimi sonrası services/index.ts bulunamadı.\n"
            "'wails3 generate bindings' çıktısını kontrol edin.")
    rel = os.path.relpath(hits[0].parent, api.parent)
    if not rel.startswith("."):
        rel = "./" + rel
    if text.count(current) != 1:
        die("ERROR:\napi.ts binding yolu birden fazla geçiyor; güvenli patch yapılamadı.")
    new = text.replace(current, rel)
    write_verified(api, new)
    if rel not in read(api):
        die("api.ts binding yolu doğrulaması başarısız")
    report.modified.append(f"frontend/src/api.ts (binding yolu → {rel})")


def go_build_with_retry(root):
    res = run(["go", "build", "./..."], cwd=root, check=False)
    if res.returncode != 0:
        combined = (res.stdout or "") + (res.stderr or "")
        if any(s in combined for s in ("missing go.sum", "updates to go.mod needed", "no required module provides")):
            print("[fix] go.sum/go.mod eksikleri → go mod tidy + tekrar build")
            run(["go", "mod", "tidy"], cwd=root)
            res = run(["go", "build", "./..."], cwd=root, check=False)
        if res.returncode != 0:
            sys.stdout.write(res.stdout or "")
            sys.stderr.write(res.stderr or "")
            die("Go build başarısız — hata çıktısı yukarıda. Dosya değişiklikleri korundu; çıktıya göre düzeltin.")
    return True


def frontend_build_with_retry(root, wails, report):
    fe = root / "frontend"
    res = run(["npm", "run", "build"], cwd=fe, check=False)
    if res.returncode != 0:
        combined = (res.stdout or "") + (res.stderr or "")
        if "bindings" in combined or "Cannot find module" in combined:
            print("[fix] binding kaynaklı frontend hatası → regenerate + heal + tekrar build")
            run([wails, "generate", "bindings"], cwd=root, env=go_env())
            heal_api_import(root, report)
            res = run(["npm", "run", "build"], cwd=fe, check=False)
        if res.returncode != 0:
            sys.stdout.write(res.stdout or "")
            sys.stderr.write(res.stderr or "")
            die("Frontend build başarısız — hata çıktısı yukarıda.")
    return True


def main():
    args = base_parser("ytdlp-studio doğrulama").parse_args()
    root = find_root(args.root)
    report = Report()
    print("PROJECT_ROOT =", root)

    ensure_tool("go", "go")
    ensure_tool("npm", "node")
    wails = ensure_wails3()

    fe = root / "frontend"
    run(["npm", "install"], cwd=fe)
    run([wails, "generate", "bindings"], cwd=root, env=go_env())
    heal_api_import(root, report)

    run(["go", "mod", "tidy"], cwd=root)
    run(["go", "fmt", "./..."], cwd=root)

    build_ok = go_build_with_retry(root)
    run(["go", "vet", "./..."], cwd=root)
    run(["go", "test", "./..."], cwd=root)
    fe_ok = frontend_build_with_retry(root, wails, report)

    dist = fe / "dist" / "index.html"
    if not dist.is_file() or dist.stat().st_size == 0:
        die("ERROR:\nfrontend/dist/index.html üretilemedi.")

    lint_result = "SKIP (lint script yok)"
    pkg = json.loads(read(fe / "package.json"))
    if "lint" in pkg.get("scripts", {}):
        res = run(["npm", "run", "lint"], cwd=fe, check=False)
        lint_result = "PASS" if res.returncode == 0 else "WARN (lint hataları var, build'i bloke etmiyor)"
        if res.returncode != 0:
            sys.stdout.write(res.stdout or "")

    report.summary("VALIDATION SUMMARY")
    print("\nValidation:")
    print(f" - Bindings: PASS (wails3 generate bindings)")
    print(f" - Go build: {'PASS' if build_ok else 'FAIL'}")
    print(" - Go vet: PASS")
    print(" - Go tests: PASS (ParseURL + DownloadOptions)")
    print(f" - Frontend build (tsc + vite): {'PASS' if fe_ok else 'FAIL'}")
    print(f" - Lint: {lint_result}")
    print("\nCompleted successfully.")
    print("\n=== GIT COMMIT MESSAGE ===\n")
    print(COMMIT_MSG)


if __name__ == "__main__":
    guard_main(main)