#!/usr/bin/env python3
# ytdlp-studio otomasyon ortak modülü — backup YOK, Markdown YOK.
import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

MARKER = "ytdlp-studio:generated v1"


class Fail(Exception):
    pass


def die(msg: str):
    raise Fail(msg)


def guard_md(path: Path):
    if path.suffix.lower() in (".md", ".markdown"):
        die(f"Markdown dosyasına dokunmak yasak: {path}")


def go_env():
    env = os.environ.copy()
    env["PATH"] = str(Path.home() / "go" / "bin") + os.pathsep + env.get("PATH", "")
    return env


def run(cmd, cwd, check=True, timeout=2400, env=None):
    print("[run]", " ".join(str(c) for c in cmd), f"(cwd={cwd})")
    res = subprocess.run([str(c) for c in cmd], cwd=str(cwd), env=env or go_env(),
                         capture_output=True, text=True, timeout=timeout)
    if check and res.returncode != 0:
        sys.stdout.write(res.stdout or "")
        sys.stderr.write(res.stderr or "")
        die(f"Komut başarısız (exit {res.returncode}): {' '.join(map(str, cmd))}")
    return res


def is_project_root(p: Path) -> bool:
    return (p / "go.mod").is_file() and (p / "main.go").is_file() and (p / "frontend" / "package.json").is_file()


def find_root(explicit=None) -> Path:
    candidates = []
    if explicit:
        candidates.append(Path(explicit).expanduser().resolve())
    cwd = Path.cwd().resolve()
    candidates += [cwd, cwd / "ytdlp-studio"]
    candidates += list(cwd.parents)[:4]
    for c in candidates:
        if is_project_root(c):
            return c
    die("Proje root'u bulunamadı (go.mod + main.go + frontend/package.json).\n"
        "Önce 00_bootstrap.py çalıştırın veya --root /path/to/proje verin.")


def base_parser(desc):
    ap = argparse.ArgumentParser(description=desc)
    ap.add_argument("--root", help="Proje kökü (verilmezse otomatik tespit)")
    return ap


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def write_verified(p: Path, content: str):
    guard_md(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    if not p.is_file() or read(p) != content:
        die(f"Dosya yazma doğrulaması başarısız: {p}")


class Report:
    def __init__(self):
        self.created, self.modified, self.deleted, self.skipped, self.notes = [], [], [], [], []

    def summary(self, title):
        print("\n=== " + title + " ===")
        for label, items in (("Created", self.created), ("Modified", self.modified),
                             ("Deleted", self.deleted), ("Skipped (idempotent)", self.skipped),
                             ("Notes", self.notes)):
            if items:
                print(f"\n{label}:")
                for i in items:
                    print(" -", i)


def write_generated(root: Path, rel: str, content: str, report: Report):
    """Yeni dosya oluştur; mevcutsa yalnızca bizim marker'ımızı taşıyorsa güncelle."""
    p = root / rel
    guard_md(p)
    if p.exists():
        existing = read(p)
        if MARKER not in existing:
            die(f"ERROR:\nBeklenmeyen mevcut dosya (generated marker yok): {rel}\n"
                f"Üzerine yazma yapılmadı. Dosyayı inceleyin.")
        if existing == content:
            report.skipped.append(rel)
            return
        write_verified(p, content)
        report.modified.append(rel)
        return
    write_verified(p, content)
    report.created.append(rel)


def replace_file(root: Path, rel: str, content: str, expect_any, report: Report):
    """Tam dosya değişimi: önce beklenen şablon yapısı doğrulanır, sonra yazılır."""
    p = root / rel
    guard_md(p)
    if p.exists():
        existing = read(p)
        if MARKER in existing:
            if existing == content:
                report.skipped.append(rel)
                return
            write_verified(p, content)
            report.modified.append(rel + " (generated güncellendi)")
            return
        if not any(s in existing for s in expect_any):
            die(f"ERROR:\nExpected structure was not found in:\n{rel}\n"
                f"Beklenen parçalardan hiçbiri yok: {expect_any}\nDosya değiştirilmedi.")
        write_verified(p, content)
        report.modified.append(rel + " (şablon değiştirildi)")
        return
    write_verified(p, content)
    report.created.append(rel)


def delete_file(root: Path, rel: str, must_contain, report: Report):
    p = root / rel
    guard_md(p)
    if not p.exists():
        report.skipped.append(rel + " (zaten yok)")
        return
    if must_contain and must_contain not in read(p):
        die(f"ERROR:\nSilme doğrulaması başarısız: {rel} beklenen '{must_contain}' içermiyor.\nSilinmedi.")
    p.unlink()
    if p.exists():
        die(f"Silme doğrulaması başarısız (hâlâ mevcut): {rel}")
    report.deleted.append(rel)


def patch_title(root: Path, report: Report):
    p = root / "frontend" / "index.html"
    if not p.is_file():
        die(f"ERROR:\nDosya yok: {p}")
    text = read(p)
    if "<title>ytdlp-studio</title>" in text:
        report.skipped.append("frontend/index.html (title zaten güncel)")
        return
    m = re.search(r"<title>.*?</title>", text, re.S)
    if not m:
        die(f"ERROR:\nBeklenen <title> bloğu bulunamadı: {p}\nPatch uygulanmadı.")
    new = text[:m.start()] + "<title>ytdlp-studio</title>" + text[m.end():]
    write_verified(p, new)
    if "<title>ytdlp-studio</title>" not in read(p):
        die("title patch doğrulaması başarısız")
    report.modified.append("frontend/index.html (title)")


def ensure_tool(name, brew_pkg):
    if shutil.which(name):
        return
    if shutil.which("brew"):
        run(["brew", "install", brew_pkg], cwd=Path.cwd())
    if not shutil.which(name):
        die(f"ERROR:\n'{name}' bulunamadı ve otomatik kurulamadı.\n"
            f"Homebrew ile: brew install {brew_pkg}")


def find_wails3():
    w = shutil.which("wails3")
    if w:
        return w
    cand = Path.home() / "go" / "bin" / "wails3"
    return str(cand) if cand.is_file() else None


def ensure_wails3():
    w = find_wails3()
    if w:
        return w
    ensure_tool("go", "go")
    run(["go", "install", "github.com/wailsapp/wails/v3/cmd/wails3@v3.0.0"], cwd=Path.cwd())
    w = find_wails3()
    if not w:
        die("ERROR:\nwails3 CLI kurulamadı (go install sonrası bulunamadı).")
    return w


def guard_main(fn):
    try:
        fn()
    except Fail as e:
        print("\nERROR:\n" + str(e), file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired as e:
        print(f"\nERROR:\nKomut zaman aşımı: {e.cmd}", file=sys.stderr)
        sys.exit(1)