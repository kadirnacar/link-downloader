#!/usr/bin/env python3
import os
import sys
import fnmatch
import argparse
from pathlib import Path
from datetime import datetime

# ==============================================================================
# ⚙️ VARSAYILAN YAPILANDIRMA
# ==============================================================================
DEFAULT_EXCLUDES = [
    "node_modules",
    "dist",
    ".git",
    "coverage",
    ".next",
    "__pycache__",
    "package-lock.json",
    "yarn.lock",
    "venv",
    ".env",
    ".DS_Store",
    "styles",
    ".pio",
    ".vscode",
    "embed",
    "vendor",
    ".cxx",
    "Pods",
    ".idea",
    "tests",
    "project_report.md"
]

DEFAULT_INCLUDES = [
    "*.hpp", 
    "*.cpp", 
    "*.c",
    "*.h", 
    "*.go", 
    "*.ini", 
    "*.json", 
    "*.js", 
    "*.ts", 
    "*.tsx", 
    "*.jsx", 
    "*.go", 
    "*.mod", 
    "*.py", 
    "*.plist", 
    "*.css", 
    # "*.gradle",
    "*.pro",
    "*.kt",
    "*.xml",
    "*.yml",
    "*.example",
    "*.sh",
    "*.bat",
    "*.ps1",
    "*.md",
    "*.html",
    "Dockerfile*",       # Dockerfile, Dockerfile.linux, Dockerfile.arm64
    ".gitignore",
    ".gitattributes",
    "*.desktop",
    "*.manifest",
    "*.command",
    # "*.swift",
    # "*.plist",
    # "*.storyboard",
    # "Podfile",
    # "*.bat"
    ]

LANG_MAP = {
    ".tsx": "tsx",
    ".ts": "typescript",
    ".css": "css",
    ".js": "javascript",
    ".py": "python",
    ".sh": "bash",
    ".zsh": "zsh",
    ".json": "json",
    ".md": "markdown",
}

# ==============================================================================
# 🛠️ YARDIMCI FONKSİYONLAR
# ==============================================================================


def is_ignored(path: Path, root: Path, excludes: list) -> bool:
    """Dosya veya dizinin exclude listesinde olup olmadığını kontrol eder."""
    try:
        # Dosyanın tarama köküne göre göreceli yolunu al
        rel_parts = path.relative_to(root).parts
        for part in rel_parts:
            if any(fnmatch.fnmatch(part, pattern) for pattern in excludes):
                return True
    except ValueError:
        # Eğer dosya root dışında bir yerdeyse (teorik olarak rglob'da zor ama güvenli)
        pass

    if any(fnmatch.fnmatch(path.name, pattern) for pattern in excludes):
        return True
    return False


def is_included(path: Path, includes: list) -> bool:
    if not includes or "*" in includes:
        return True
    return any(fnmatch.fnmatch(path.name, pattern) for pattern in includes)


# ==============================================================================
# 🚀 ANA SCRIPT
# ==============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="🚀 Birden fazla dizini tarayıp tek bir Markdown raporu oluşturur.",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # 'dir' artık liste kabul ediyor (nargs='+')
    parser.add_argument(
        "dirs", nargs="+", help="Taranacak dizinler (Örn: ./src ./lib ./config)"
    )
    parser.add_argument(
        "-o", "--output", default="project_report.md", help="Çıktı dosya adı"
    )
    parser.add_argument(
        "-i",
        "--include",
        nargs="+",
        default=DEFAULT_INCLUDES,
        help="Dahil edilecek desenler",
    )
    parser.add_argument(
        "-e",
        "--exclude",
        nargs="+",
        default=DEFAULT_EXCLUDES,
        help="Hariç tutulacak desenler",
    )
    parser.add_argument(
        "-s", "--max-size", type=int, default=500, help="Maksimum dosya boyutu (KB)"
    )
    parser.add_argument(
        "-d", "--days", type=int, default=0, help="Son X günde değişenler"
    )

    args = parser.parse_args()

    all_found_files = []

    # 1. Her bir dizini sırayla tara
    for d in args.dirs:
        search_path = Path(d).resolve()
        if not search_path.is_dir():
            print(f"⚠️ Uyarı: '{d}' geçerli bir dizin değil, atlanıyor.")
            continue

        print(f"🔍 Tarama: {search_path}")

        for file_path in search_path.rglob("*"):
            if not file_path.is_file():
                continue

            if is_ignored(file_path, search_path, args.exclude):
                continue
            if not is_included(file_path, args.include):
                continue
            if file_path.stat().st_size > args.max_size * 1024:
                continue
            if args.days > 0:
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if (datetime.now() - mtime).days > args.days:
                    continue

            # (Dosya objesi, arandığı kök dizin) şeklinde sakla ki relative_path doğru hesaplansın
            all_found_files.append((file_path, search_path))

    if not all_found_files:
        print("❌ Kriterlere uygun dosya bulunamadı!")
        return

    # 2. Markdown Yazımı
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(f"# 📂 Çoklu Dizin Proje Raporu\n\n")
        f.write(f"- **Tarih:** {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n")
        f.write(f"- **Taranan Dizinler:** `{', '.join(args.dirs)}`\n\n")

        f.write("## 📑 İçindekiler\n")
        f.write("| # | Kaynak Dizin | Dosya Yolu | Tür | Satır |\n")
        f.write("|---|--------------|------------|-----|-------|\n")

        details = []
        total_lines = 0

        for idx, (path, root) in enumerate(all_found_files, 1):
            rel_path = path.relative_to(root)
            root_name = root.name
            ext = path.suffix.lower()
            lang = LANG_MAP.get(ext, "")

            try:
                raw_content = path.read_text(encoding="utf-8")
                line_count = len(raw_content.splitlines())
            except Exception:
                raw_content = "⚠️ Dosya okunamadı veya binary."
                line_count = 0

            total_lines += line_count
            # Çakışmaları önlemek için anchor'a root ismini de ekleyelim
            anchor = (
                f"{root_name}-{str(rel_path)}".replace(".", "-")
                .replace("/", "-")
                .replace("\\", "-")
            )

            f.write(
                f"| {idx} | {root_name} | [{rel_path}](#{anchor}) | {ext.upper()} | {line_count} |\n"
            )

            details.append(
                f"\n---\n### 📄 {root_name} / {rel_path} <a name='{anchor}'></a>\n"
            )
            details.append(f"📏 **Satır:** {line_count} | 📂 **Kök:** `{root}`\n")
            details.append(f"```{lang}\n{raw_content}\n```\n")
            print(f" ✅ İşlendi: {root_name}/{rel_path}")

        f.write("\n" + "".join(details))
        f.write(
            f"\n---\n## 📊 Özet\n- Toplam Dosya: {len(all_found_files)}\n- Toplam Satır: {total_lines}\n"
        )

    print(f"\n✨ İşlem tamamlandı! {args.output} oluşturuldu.")


if __name__ == "__main__":
    main()
