#!/usr/bin/env python3
"""
ytdlp-studio · Cross-compile düzeltmeleri

1. build/docker/Dockerfile.cross → Go 1.27 sürümüne yükselt
2. services/download.go → Reveal fonksiyonunu cross-platform yap (macOS/Windows/Linux)

Backup oluşturmaz. Markdown üretmez.
"""

import re
import sys
from pathlib import Path

ROOT = None
MODIFIED = []


def find_project_root():
    current = Path.cwd()
    while current != current.parent:
        if (current / "go.mod").exists() and (current / "Taskfile.yml").exists():
            return current
        current = current.parent
    raise SystemExit("ERROR: Proje kökü bulunamadı.")


def rel(p):
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def fail(msg):
    print("\nERROR:")
    print(msg)
    sys.exit(1)


def read(p):
    if not p.exists():
        fail(f"Dosya bulunamadı:\n{p}")
    return p.read_text(encoding="utf-8")


def write(p, content):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


# --------------------------------------------------------------------------- #
# 1. Dockerfile.cross — Go 1.27
# --------------------------------------------------------------------------- #
def patch_dockerfile():
    path = ROOT / "build" / "docker" / "Dockerfile.cross"
    if not path.exists():
        fail(f"Dockerfile.cross bulunamadı: {path}")

    content = read(path)

    # Go sürümünü 1.26'dan 1.27'ye yükselt
    if "golang:1.26" in content:
        content = content.replace("golang:1.26", "golang:1.27")
        write(path, content)
        MODIFIED.append("build/docker/Dockerfile.cross (Go 1.26 → 1.27)")
        print("UPDATED : build/docker/Dockerfile.cross")
    elif "golang:1.27" in content:
        print("ALREADY : build/docker/Dockerfile.cross (Go 1.27)")
    else:
        fail("Dockerfile.cross içinde beklenen golang:1.2x kalıbı bulunamadı.")


# --------------------------------------------------------------------------- #
# 2. services/download.go — Reveal cross-platform
# --------------------------------------------------------------------------- #
DOWNLOAD_GO_REVEAL = '''func (d *DownloadService) Reveal(path string) error {
	if path == "" {
		return errors.New("dosya yolu boş")
	}
	st, err := os.Stat(path)
	switch {
	case err == nil && st.IsDir():
		return revealPath(path, false)
	case err == nil:
		return revealPath(path, true)
	default:
		dir := filepath.Dir(path)
		if _, e := os.Stat(dir); e == nil {
			return revealPath(dir, false)
		}
		return fmt.Errorf("dosya bulunamadı: %s", path)
	}
}

func revealPath(path string, selectFile bool) error {
	switch runtime.GOOS {
	case "darwin":
		if selectFile {
			return exec.Command("open", "-R", path).Run()
		}
		return exec.Command("open", path).Run()
	case "windows":
		if selectFile {
			return exec.Command("explorer.exe", "/select,", path).Run()
		}
		return exec.Command("explorer.exe", path).Run()
	case "linux":
		// xdg-open genellikle dizinleri ve dosyaları açabilir
		if selectFile {
			dir := filepath.Dir(path)
			return exec.Command("xdg-open", dir).Run()
		}
		return exec.Command("xdg-open", path).Run()
	default:
		return fmt.Errorf("bu özellik %s platformunda desteklenmiyor", runtime.GOOS)
	}
}
'''


def patch_download_reveal():
    path = ROOT / "services" / "download.go"
    content = read(path)

    # Mevcut Reveal fonksiyonunu bul ve değiştir
    pattern = r'func \(d \*DownloadService\) Reveal\(path string\) error \{[^}]+\n\t\}\n\}'
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)

    if not match:
        # Basit pattern ile dene
        if "func (d *DownloadService) Reveal(path string) error" not in content:
            fail("Reveal fonksiyonu bulunamadı.")
        # Manuel bulma
        start = content.index("func (d *DownloadService) Reveal(path string) error")
        # Eşleşen parantezleri sayarak sonu bul
        depth = 0
        end = start
        in_func = False
        for i, ch in enumerate(content[start:], start):
            if ch == '{':
                depth += 1
                in_func = True
            elif ch == '}':
                depth -= 1
                if in_func and depth == 0:
                    end = i + 1
                    break

        old_func = content[start:end]
    else:
        old_func = match.group(0)

    # revealPath yardımcı fonksiyonu zaten var mı?
    has_reveal_path = "func revealPath(path string, selectFile bool) error" in content

    if old_func in content and not has_reveal_path:
        # Reveal fonksiyonunu ve yeni revealPath'i ekle
        new_content = content.replace(old_func, DOWNLOAD_GO_REVEAL)
        write(path, new_content)
        MODIFIED.append("services/download.go (Reveal cross-platform)")
        print("UPDATED : services/download.go")
    elif has_reveal_path:
        print("ALREADY : services/download.go (revealPath mevcut)")
    else:
        fail("Reveal fonksiyonu değiştirilemedi.")


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    global ROOT
    ROOT = find_project_root()
    print(f"Project root: {ROOT}\n")

    print("=== Dockerfile.cross Go sürümü ===")
    patch_dockerfile()

    print("\n=== DownloadService.Reveal cross-platform ===")
    patch_download_reveal()

    print("\n=== UPDATE SUMMARY ===")
    print("Modified:")
    for m in MODIFIED:
        print(f"  - {m}")

    print("\nŞimdi cross-compile komutlarını tekrar çalıştırabilirsiniz:")
    print("  GOOS=linux GOARCH=amd64 task build")
    print("  GOOS=windows GOARCH=amd64 task build")

    print("\n=== GIT COMMIT MESSAGE ===")
    print(
        "fix(cross-compile): upgrade Docker Go to 1.27 and cross-platform Reveal\n"
        "\n"
        "- Update Dockerfile.cross from golang:1.26 to golang:1.27 (go.mod requirement)\n"
        "- Make DownloadService.Reveal work on macOS, Windows, and Linux\n"
        "- Add revealPath helper with platform-specific commands\n"
        "- macOS: open / open -R\n"
        "- Windows: explorer.exe / explorer.exe /select,\n"
        "- Linux: xdg-open\n"
    )


if __name__ == "__main__":
    main()