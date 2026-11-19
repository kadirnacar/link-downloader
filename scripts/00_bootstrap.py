#!/usr/bin/env python3
# ytdlp-studio:bootstrap-fix-v1
# 00_bootstrap.py — proje root tespiti + gerekirse Wails v3 react (TypeScript) iskeleti.
import shutil
import sys
from pathlib import Path

from _common import (Fail, Report, base_parser, die, ensure_tool, ensure_wails3,
                     find_root, go_env, guard_main, is_project_root, read, run)


def main():
    args = base_parser("ytdlp-studio bootstrap").parse_args()
    report = Report()

    root = None
    try:
        root = find_root(args.root)
    except Fail:
        root = None

    if root:
        print("Mevcut proje bulundu:", root)
        gomod = read(root / "go.mod")
        if "github.com/wailsapp/wails/v3" not in gomod:
            die("Bu otomasyon Wails v3 projeleri içindir; go.mod içinde wails/v3 bulunamadı.\n"
                "v2 projesi yanlışlıkla değiştirilmedi.")
        report.notes.append(f"Mevcut proje doğrulandı: {root}")
    else:
        parent = Path(args.root).expanduser().resolve() if args.root else Path.cwd()
        parent.mkdir(parents=True, exist_ok=True)
        print("Proje yok → sıfırdan iskelet kurulacak:", parent)
        ensure_tool("go", "go")
        ensure_tool("node", "node")
        ensure_tool("npm", "node")
        wails = ensure_wails3()
        init_ok = False
        last_out = ""
        for tpl in ("react", "react-ts"):
            target = parent / "ytdlp-studio"
            if target.exists():
                if is_project_root(target):
                    init_ok = True
                    break
                if any(target.iterdir()):
                    die(f"ERROR:\nHedef dizin dolu ama proje değil: {target}\nİçeriği inceleyin; otomatik silme yapılmadı.")
                target.rmdir()
            res = run([wails, "init", "-n", "ytdlp-studio", "-t", tpl], cwd=parent, env=go_env(), check=False)
            last_out = (res.stdout or "") + (res.stderr or "")
            if res.returncode == 0:
                init_ok = True
                break
            if "invalid remote git URL" not in last_out and "invalid template" not in last_out:
                sys.stdout.write(last_out)
                die(f"wails3 init başarısız (template={tpl}). Çıktı yukarıda.")
        if not init_ok:
            sys.stdout.write(last_out)
            die("Yerleşik React şablonu bulunamadı. 'wails3 init -l' ile şablon adlarını kontrol edin.")
        root = parent / "ytdlp-studio"
        if not is_project_root(root):
            die(f"ERROR:\nwails3 init sonrası proje yapısı doğrulanamadı: {root}\n"
                "go.mod / main.go / frontend/package.json eksik.")
        report.created.append(str(root) + " (wails3 react-ts iskeleti)")

    ensure_tool("go", "go")
    ensure_tool("node", "node")
    ensure_tool("npm", "node")
    ensure_wails3()
    report.notes.append("Araç zinciri hazır: go, node, npm, wails3")
    report.notes.append(f"PROJECT_ROOT={root}")
    report.summary("BOOTSTRAP SUMMARY")
    print("\nSonraki adım: python3 scripts/01_apply_changes.py")


if __name__ == "__main__":
    guard_main(main)