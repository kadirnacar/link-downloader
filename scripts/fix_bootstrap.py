#!/usr/bin/env python3
# fix_bootstrap.py — 00_bootstrap.py'deki geçersiz 'react-ts' şablon adını
# Wails v3 yerleşik 'react' (TypeScript) şablonuyla değiştirir.
# Backup YOK, Markdown YOK, idempotent.
import re
import sys
from pathlib import Path

FIX_MARKER = "ytdlp-studio:bootstrap-fix-v1"

OLD_INIT = '        run([wails, "init", "-n", "ytdlp-studio", "-t", "react-ts"], cwd=parent, env=go_env())\n'

NEW_INIT = r'''        init_ok = False
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
'''

COMMIT_MSG = """fix(bootstrap): use Wails v3 built-in react template instead of invalid react-ts

- replace 'wails3 init -t react-ts' (unknown name treated as remote git URL in v3.0.0) with built-in 'react' (TypeScript) template
- add template fallback loop, empty leftover-dir cleanup and init failure output reporting
- add sys import for failure output; update bootstrap header comment
"""


def die(msg):
    print("\nERROR:\n" + msg, file=sys.stderr)
    sys.exit(1)


def main():
    target = Path(__file__).resolve().parent / "00_bootstrap.py"
    if not target.is_file():
        die(f"Dosya yok: {target}")
    text = target.read_text(encoding="utf-8")

    # 1) Idempotency kontrolleri
    if FIX_MARKER in text:
        print("Skipped (idempotent): fix zaten uygulanmış.")
        return
    if OLD_INIT not in text and '"-t", "react"' in text:
        print("Skipped: init satırı zaten 'react' şablonunu kullanıyor.")
        return

    # 2) Beklenen mevcut içeriği doğrula
    if text.count(OLD_INIT) != 1:
        die(f"Expected code block was not found in:\n{target}\n"
            f"Beklenen init satırı birebir bulunamadı (count={text.count(OLD_INIT)}).\n"
            "Patch uygulanmadı.")
    if "import shutil\n" not in text:
        die("'import shutil' satırı bulunamadı; güvenli patch yapılamadı.\nPatch uygulanmadı.")
    if "#!/usr/bin/env python3\n" not in text:
        die("Shebang satırı bulunamadı; marker eklenemiyor.\nPatch uygulanmadı.")

    # 3) Patch'i bellekte uygula
    new = text.replace(OLD_INIT, NEW_INIT, 1)
    if re.search(r"(?m)^import sys$", new) is None:
        new = new.replace("import shutil\n", "import shutil\nimport sys\n", 1)
    new = new.replace("Wails v3 react-ts iskeleti", "Wails v3 react (TypeScript) iskeleti")
    new = new.replace("#!/usr/bin/env python3\n",
                      "#!/usr/bin/env python3\n# " + FIX_MARKER + "\n", 1)

    # 4) Yazmadan ÖNCE doğrula (backup yok, bu yüzden önce kanıtla)
    if FIX_MARKER not in new or OLD_INIT in new or "for tpl in" not in new:
        die("Patch ön-doğrulaması başarısız. Dosya değiştirilmedi.")
    try:
        compile(new, str(target), "exec")
    except SyntaxError as e:
        die(f"Patch sonrası sözdizimi hatası: {e}\nDosya değiştirilmedi.")

    # 5) Yaz ve son durumu doğrula
    target.write_text(new, encoding="utf-8")
    if target.read_text(encoding="utf-8") != new:
        die("Patch yazma doğrulaması başarısız (içerik eşleşmiyor).")

    print("\n=== FIX SUMMARY ===")
    print("\nModified:")
    print(f" - {target}")
    print("   * '-t react-ts' → yerleşik 'react' (TypeScript) + fallback döngüsü")
    print("   * boş kalıntı dizin temizliği + init hata çıktısı raporlama")
    print("   * 'import sys' eklendi, başlık yorumu güncellendi")
    print("\nValidation:")
    print(" - Expected-block check: PASS")
    print(" - Syntax check (compile): PASS")
    print(" - Post-write verify: PASS")
    print("\nCompleted successfully.")
    print("\n=== GIT COMMIT MESSAGE ===\n")
    print(COMMIT_MSG)


if __name__ == "__main__":
    main()