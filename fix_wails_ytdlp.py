#!/usr/bin/env python3
import sys
from pathlib import Path

def find_project_root():
    current = Path.cwd()
    while current != current.parent:
        if (current / "go.mod").exists() and (current / "Taskfile.yml").exists():
            return current
        current = current.parent
    return None

ROOT = find_project_root()
if not ROOT:
    print("HATA: Proje kök dizini bulunamadı (go.mod veya Taskfile.yml eksik)")
    sys.exit(1)

print(f"Proje kök dizini tespit edildi: {ROOT}")

def patch_file(rel_path, old_content, new_content, description):
    file_path = ROOT / rel_path
    if not file_path.exists():
        print(f"HATA: Dosya bulunamadı: {file_path}")
        sys.exit(1)
        
    content = file_path.read_text(encoding='utf-8')
    if old_content not in content:
        if new_content in content:
            print(f"ZATEN UYGULANDI: {description}")
            return
        print(f"HATA: Beklenen kod bloğu bulunamadı: {file_path}\nİşlem: {description}")
        sys.exit(1)
        
    new_content_full = content.replace(old_content, new_content)
    file_path.write_text(new_content_full, encoding='utf-8')
    print(f"YAMALANDI: {file_path.name} - {description}")

# 1. PreviewList.tsx - Null safety for info.entries in filter
old_filter = """  if (!info) {
    return <section className="preview empty">URL yapıştırdığında içerik önizlemesi burada görünür.</section>;
  }

  const visible = info.entries.filter((e) => e.title.toLowerCase().includes(filter.toLowerCase()));"""
new_filter = """  if (!info) {
    return <section className="preview empty">URL yapıştırdığında içerik önizlemesi burada görünür.</section>;
  }
  const entries = info.entries ?? [];
  const visible = entries.filter((e) => e.title.toLowerCase().includes(filter.toLowerCase()));"""

patch_file("frontend/src/components/PreviewList.tsx", old_filter, new_filter, "info.entries null kontrolü (filter)")

# 2. PreviewList.tsx - Null safety for info.entries length
old_length = """        <span className="count">
          {selected.size}/{info.entries.length}
        </span>"""
new_length = """        <span className="count">
          {selected.size}/{entries.length}
        </span>"""

patch_file("frontend/src/components/PreviewList.tsx", old_length, new_length, "info.entries null kontrolü (length)")

print("\n=== GÜNCELLEME ÖZETİ ===")
print("Değiştirilen Dosyalar:")
print("- frontend/src/components/PreviewList.tsx: info.entries null/undefined kontrolleri (?? []) eklendi.")
print("\nDoğrulama:")
print("- `wails3 dev` veya `cd frontend && npm run build`")