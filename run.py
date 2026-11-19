#!/usr/bin/env python3
"""
ytdlp-studio · README.md cross-compile bölümü güncelleyici

- README.md içine marker'lı "Cross-Compile (macOS -> Windows / Linux)" bölümü ekler.
- Bölüm zaten varsa yalnızca o bölümü değiştirir (idempotent).
- README.md yoksa hata verir (önce create_github_readme.py çalıştırılmalı).
- Backup oluşturmaz; başka dosyaya dokunmaz.
"""

import sys
from pathlib import Path

ROOT = None
START = "<!-- ytdlp-studio:xcompile v1 -->"
END = "<!-- ytdlp-studio:xcompile v1:end -->"
ANCHOR = "## 🧯 Sorun Giderme"

SECTION = (
    START
    + """
## 🌍 Cross-Compile (macOS → Windows / Linux)

Wails v3, kök `Taskfile.yml` üzerindeki `GOOS` değişkeni ile görevleri platform
Taskfile'lerine dispatch eder (`windows:`, `linux:`, `darwin:`…). Host işletim
sisteminden farklı bir hedef seçildiğinde derleme, `task setup:docker` ile kurulan
cross-compile Docker imajı içinde gerçekleştirilir.

### Ön hazırlık (tek seferlik)

```bash
task setup:docker     # ~800 MB cross-compile imajı (Linux/Windows araç zincirleri)
wails3 doctor         # ortam doğrulaması
```

### Windows hedefi (macOS üzerinden)

```bash
# Derleme (portable EXE)
GOOS=windows GOARCH=amd64 task build
# eşdeğeri:
wails3 build GOOS=windows GOARCH=amd64
# çıktı: bin/ytdlp-studio.exe
```

- Windows hedefi CGO gerektirmez; hedef makinede **WebView2 Runtime** bulunmalıdır.
- **Paketleme (MSIX):** `makeappx`/`signtool` gibi Windows SDK araçları gerektirir, macOS'ta
  üretilemez. MSIX için bir Windows makinesinde veya CI'da (GitHub Actions `windows-latest`)
  `task install:msix:tools` + `task package` çalıştırın; ya da `bin/ytdlp-studio.exe`
  dosyasını portable olarak dağıtın.

### Linux hedefi (macOS üzerinden)

```bash
# Derleme
GOOS=linux GOARCH=amd64 task build
# Paketleme (çıktı yolu için build/linux/Taskfile.yml / task --list-all)
GOOS=linux GOARCH=amd64 task package
```

- Linux GUI hedefi CGO + WebKitGTK başlıkları gerektirdiğinden **Docker imajı zorunludur**
  (`task setup:docker`).
- Hedef makinede `libwebkit2gtk-4.1` çalışma zamanı kütüphaneleri bulunmalıdır.

### Mimari varyantları

```bash
GOOS=linux GOARCH=arm64 task build      # örn. Raspberry Pi / ARM sunucu
GOOS=windows GOARCH=arm64 task build    # Windows on ARM
```

### Headless / server modu (GUI'siz, CGO'suz)

```bash
GOOS=linux GOARCH=amd64 task build:server   # yalnızca HTTP sunucu
task build:docker                            # server modu için Docker imajı
task run:docker                              # imajı çalıştır
```

Server modu WebKit/CGO gerektirmez; düz Go cross-compile ile her platforma üretilebilir.

### Cross-compile notları

- Frontend (`frontend/dist`) platformdan bağımsızdır ve binary'ye gömülür (`//go:embed`).
- yt-dlp / ffmpeg / ffprobe / bun, hedef platforma uygun sürümleriyle **çalışma zamanında**
  otomatik indirilir; cross-build imajına dahil etmenize gerek yoktur.
- `DownloadService.Reveal` ("Finder'da göster") şu an yalnızca macOS'ta çalışır;
  Windows/Linux hedeflerinde hata döner.
- CI önerisi: matrix kullanarak `windows-latest` üzerinde `task package` (MSIX dahil),
  `ubuntu-latest` + Docker imajı ile `GOOS=linux task build/package`.
"""
    + END
)


def find_project_root() -> Path:
    current = Path.cwd()
    while current != current.parent:
        if (current / "go.mod").exists() and (current / "Taskfile.yml").exists():
            return current
        current = current.parent
    raise SystemExit("ERROR: Proje kökü bulunamadı (go.mod + Taskfile.yml aranıyor).")


def fail(msg: str) -> None:
    print("\nERROR:")
    print(msg)
    sys.exit(1)


def main() -> None:
    global ROOT
    ROOT = find_project_root()
    readme = ROOT / "README.md"

    if not readme.exists():
        fail(
            "README.md bulunamadı.\n"
            f"Dosya: {readme}\n"
            "Önce create_github_readme.py scriptini çalıştırın."
        )

    content = readme.read_text(encoding="utf-8")

    if START in content and END in content:
        i = content.index(START)
        j = content.index(END) + len(END)
        new = content[:i] + SECTION + content[j:]
        action = "mevcut cross-compile bölümü değiştirildi"
    else:
        if ANCHOR in content:
            i = content.index(ANCHOR)
            new = content[:i] + SECTION + "\n\n" + content[i:]
        else:
            new = content.rstrip() + "\n\n" + SECTION + "\n"
        action = "cross-compile bölümü eklendi"

    readme.write_text(new, encoding="utf-8")

    # doğrulama
    v = readme.read_text(encoding="utf-8")
    if v.count(START) != 1 or v.count(END) != 1:
        fail("Marker sayısı beklenenden farklı (bölüm çift yazılmış olabilir).")
    for needle in ("task setup:docker", "GOOS=windows", "GOOS=linux", "build:server", "MSIX"):
        if needle not in v:
            fail(f"README doğrulaması başarısız, eksik içerik: {needle}")

    print(f"UPDATED : README.md ({action})")
    print("\n=== UPDATE SUMMARY ===")
    print("Modified:")
    print("  - README.md (cross-compile bölümü: Windows/Linux/ARM + server modu + MSIX notları)")
    print("\nValidation:")
    print("  - README marker ve içerik doğrulaması: PASS")
    print("\nCompleted successfully.")

    print("\n=== GIT COMMIT MESSAGE ===")
    print(
        "docs(readme): add cross-compilation guide for Windows and Linux targets\n"
        "\n"
        "- Document task setup:docker cross-compile image usage\n"
        "- Add GOOS/GOARCH build & package commands for windows/linux amd64+arm64\n"
        "- Note MSIX packaging restriction (Windows SDK tools) and CI alternative\n"
        "- Note Linux CGO/WebKitGTK requirement and per-target runtime deps\n"
        "- Document headless server-mode cross builds (build:server, build:docker)\n"
    )


if __name__ == "__main__":
    main()
