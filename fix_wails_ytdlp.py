#!/usr/bin/env python3
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = None


def find_project_root():
    current = Path.cwd()
    while current != current.parent:
        if (current / "go.mod").exists() and (current / "Taskfile.yml").exists():
            return current
        current = current.parent
    return None


PROJECT_ROOT = find_project_root()
if PROJECT_ROOT is None:
    print("ERROR: Proje kökü bulunamadı. Bu scripti proje kökünde çalıştırın.")
    sys.exit(1)

print(f"Project root: {PROJECT_ROOT}")


def fail(message: str):
    print(f"\nERROR:\n{message}\n")
    sys.exit(1)


def run_cmd(cmd, cwd=None):
    printable = " ".join(str(x) for x in cmd)
    print(f"$ {printable}")
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
    )
    if proc.stdout:
        print(proc.stdout)
    if proc.stderr:
        print(proc.stderr)
    return proc.returncode == 0


def read_text(path: Path) -> str:
    if not path.exists():
        fail(f"Dosya bulunamadı:\n{path}")
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"UPDATED: {path.relative_to(PROJECT_ROOT)}")


HELPER_MARKER = "// ytdlp-studio:playlist-all v2"
ANALYZE_MARKER = "// ytdlp-studio:playlist-all-analyze v2"
THUMB_MARKER = "// ytdlp-studio:playlist-all-thumb v2"

HELPER_GO = '''// ytdlp-studio:playlist-all v2
package services

import (
	"reflect"
	"strconv"
	"strings"

	"github.com/lrstanley/go-ytdlp"
	"ytdlp-studio/internal/model"
)

func plAllHasEntries(e *ytdlp.ExtractedInfo) bool {
	if e == nil {
		return false
	}
	return len(e.Entries) > 0
}

func plAllFlatten(infos []*ytdlp.ExtractedInfo) []*ytdlp.ExtractedInfo {
	var out []*ytdlp.ExtractedInfo

	var walk func(e *ytdlp.ExtractedInfo, depth int)
	walk = func(e *ytdlp.ExtractedInfo, depth int) {
		if e == nil {
			return
		}
		if len(e.Entries) == 0 || depth > 8 {
			out = append(out, e)
			return
		}
		for _, child := range e.Entries {
			walk(child, depth+1)
		}
	}

	for _, info := range infos {
		walk(info, 0)
	}

	return out
}

func plAllDedupe(infos []*ytdlp.ExtractedInfo) []*ytdlp.ExtractedInfo {
	seen := make(map[string]bool)
	var out []*ytdlp.ExtractedInfo

	for _, e := range infos {
		if e == nil {
			continue
		}

		id := plAllString(e, "ID", "")
		url := plAllString(e, "WebpageURL", "")
		key := id + "|" + url

		if key == "|" {
			out = append(out, e)
			continue
		}
		if seen[key] {
			continue
		}
		seen[key] = true
		out = append(out, e)
	}

	return out
}

func plAllPlaylistTitle(infos []*ytdlp.ExtractedInfo, fallback string) string {
	if len(infos) == 0 {
		if fallback != "" {
			return fallback
		}
		return "Playlist"
	}

	root := infos[0]
	if plAllHasEntries(root) {
		if t := plAllString(root, "Title", ""); t != "" {
			return t
		}
	}

	fields := []string{"PlaylistTitle", "Playlist", "Album", "Uploader", "Channel"}
	for _, info := range infos {
		if info == nil {
			continue
		}
		for _, f := range fields {
			if t := plAllString(info, f, ""); t != "" {
				return t
			}
		}
	}

	if root != nil {
		if t := plAllString(root, "Title", ""); t != "" {
			return t
		}
	}

	if fallback != "" {
		return fallback
	}
	return "Playlist"
}

func plAllFirstTitle(infos []*ytdlp.ExtractedInfo) string {
	for _, e := range infos {
		if e == nil {
			continue
		}
		if t := plAllString(e, "Title", ""); t != "" {
			return t
		}
	}
	return ""
}

func plAllIsUnavailable(title string) bool {
	if title == "" {
		return true
	}
	lower := strings.ToLower(title)
	return strings.Contains(lower, "[private video]") ||
		strings.Contains(lower, "[deleted video]") ||
		strings.Contains(lower, "private video") ||
		strings.Contains(lower, "deleted video") ||
		strings.Contains(lower, "unavailable")
}

func plAllEntry(index int, e *ytdlp.ExtractedInfo) model.MediaEntry {
	id := plAllString(e, "ID", "")
	url := plAllString(e, "WebpageURL", "")
	title := plAllString(e, "Title", "")
	duration := plAllFloat(e, "Duration", 0)

	if idx := plAllInt(e, "PlaylistIndex", 0); idx > 0 {
		index = idx
	}

	displayTitle := title
	if displayTitle == "" {
		displayTitle = id
	}

	available := id != "" && !plAllIsUnavailable(title)

	return model.MediaEntry{
		ID:          id,
		URL:         url,
		Title:       displayTitle,
		DurationSec: duration,
		Thumbnail:   "",
		Index:       index,
		Available:   available,
	}
}

func plAllThumbnail(e *ytdlp.ExtractedInfo) string {
	if e == nil {
		return ""
	}

	f := plAllField(reflect.ValueOf(e), "Thumbnails")
	if f.IsValid() {
		if f.Kind() == reflect.Ptr || f.Kind() == reflect.Interface {
			if !f.IsNil() {
				f = f.Elem()
			}
		}
		if f.Kind() == reflect.Slice {
			for i := f.Len() - 1; i >= 0; i-- {
				item := f.Index(i)
				if u := plAllStringFromValue(item, "URL", ""); u != "" {
					return u
				}
			}
		}
	}

	id := plAllString(e, "ID", "")
	if len(id) == 11 {
		return "https://i.ytimg.com/vi/" + id + "/hqdefault.jpg"
	}
	return ""
}

func plAllStringFromValue(v reflect.Value, name string, fallback string) string {
	if !v.IsValid() {
		return fallback
	}
	f := plAllField(v, name)
	if !f.IsValid() {
		return fallback
	}
	return plAllValueString(f, fallback)
}

func plAllString(e *ytdlp.ExtractedInfo, name string, fallback string) string {
	if e == nil {
		return fallback
	}
	f := plAllField(reflect.ValueOf(e), name)
	if !f.IsValid() {
		return fallback
	}
	return plAllValueString(f, fallback)
}

func plAllFloat(e *ytdlp.ExtractedInfo, name string, fallback float64) float64 {
	if e == nil {
		return fallback
	}
	f := plAllField(reflect.ValueOf(e), name)
	if !f.IsValid() {
		return fallback
	}
	return plAllValueFloat(f, fallback)
}

func plAllInt(e *ytdlp.ExtractedInfo, name string, fallback int) int {
	if e == nil {
		return fallback
	}
	f := plAllField(reflect.ValueOf(e), name)
	if !f.IsValid() {
		return fallback
	}
	return plAllValueInt(f, fallback)
}

func plAllField(v reflect.Value, name string) reflect.Value {
	switch v.Kind() {
	case reflect.Ptr, reflect.Interface:
		if v.IsNil() {
			return reflect.Value{}
		}
		return plAllField(v.Elem(), name)
	case reflect.Struct:
		f := v.FieldByName(name)
		if f.IsValid() {
			return f
		}

		t := v.Type()
		for i := 0; i < t.NumField(); i++ {
			sf := t.Field(i)
			if !sf.Anonymous || sf.PkgPath != "" {
				continue
			}
			if res := plAllField(v.Field(i), name); res.IsValid() {
				return res
			}
		}
	}
	return reflect.Value{}
}

func plAllValueString(f reflect.Value, fallback string) string {
	switch f.Kind() {
	case reflect.String:
		return f.String()
	case reflect.Ptr, reflect.Interface:
		if f.IsNil() {
			return fallback
		}
		return plAllValueString(f.Elem(), fallback)
	case reflect.Float32, reflect.Float64:
		return strconv.FormatFloat(f.Float(), 'f', -1, 64)
	case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
		return strconv.FormatInt(f.Int(), 10)
	case reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64:
		return strconv.FormatUint(f.Uint(), 10)
	}
	return fallback
}

func plAllValueFloat(f reflect.Value, fallback float64) float64 {
	switch f.Kind() {
	case reflect.Float32, reflect.Float64:
		return f.Float()
	case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
		return float64(f.Int())
	case reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64:
		return float64(f.Uint())
	case reflect.String:
		if parsed, err := strconv.ParseFloat(strings.TrimSpace(f.String()), 64); err == nil {
			return parsed
		}
	case reflect.Ptr, reflect.Interface:
		if f.IsNil() {
			return fallback
		}
		return plAllValueFloat(f.Elem(), fallback)
	}
	return fallback
}

func plAllValueInt(f reflect.Value, fallback int) int {
	switch f.Kind() {
	case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
		return int(f.Int())
	case reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64:
		return int(f.Uint())
	case reflect.Float32, reflect.Float64:
		return int(f.Float())
	case reflect.String:
		if parsed, err := strconv.Atoi(strings.TrimSpace(f.String())); err == nil {
			return parsed
		}
	case reflect.Ptr, reflect.Interface:
		if f.IsNil() {
			return fallback
		}
		return plAllValueInt(f.Elem(), fallback)
	}
	return fallback
}
'''

NEW_ANALYZE_FUNC = '''// ytdlp-studio:playlist-all-analyze v2
func (s *AnalyzeService) Analyze(raw, scope string) (*model.MediaInfo, error) {
	p, err := s.ParseURL(raw)
	if err != nil {
		return nil, err
	}

	target := p.CanonicalURL
	wantPlaylist := false

	switch {
	case p.Kind == "playlist" || (p.Ambiguous && scope == "playlist"):
		target = "https://www.youtube.com/playlist?list=" + p.ListID
		wantPlaylist = true
	case p.VideoID != "":
		target = "https://www.youtube.com/watch?v=" + p.VideoID
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Minute)
	defer cancel()

	infos, _, err := engine.NewCommand().FlatPlaylist().ExtractInfo(ctx, target)
	if err != nil {
		return nil, fmt.Errorf("içerik analizi başarısız: %w", err)
	}
	if len(infos) == 0 {
		return nil, errors.New("içerik bulunamadı")
	}

	entries := plAllDedupe(plAllFlatten(infos))
	if len(entries) == 0 {
		return nil, errors.New("içerik bulunamadı")
	}

	kind := "video"
	id := p.VideoID
	title := ""

	if wantPlaylist || p.Kind == "playlist" || len(entries) > 1 || plAllHasEntries(infos[0]) {
		kind = "playlist"
		id = p.ListID
		title = plAllPlaylistTitle(infos, p.ListID)

		if id == "" {
			id = plAllString(infos[0], "PlaylistID", "")
		}
		if id == "" && len(entries) > 0 {
			id = plAllString(entries[0], "PlaylistID", "")
		}
		if id == "" {
			id = "playlist"
		}
	} else {
		id = plAllString(infos[0], "ID", p.VideoID)
		title = plAllString(infos[0], "Title", "")
	}

	if title == "" {
		title = plAllFirstTitle(entries)
	}
	if title == "" {
		title = id
	}

	out := &model.MediaInfo{Kind: kind, ID: id, Title: title}

	for i, e := range entries {
		if e == nil {
			continue
		}

		me := plAllEntry(i+1, e)
		if me.URL == "" && me.ID != "" {
			me.URL = "https://www.youtube.com/watch?v=" + me.ID
		}
		me.Thumbnail = thumbOf(e)
		out.Entries = append(out.Entries, me)
	}

	return out, nil
}
'''

NEW_THUMB_FUNC = '''// ytdlp-studio:playlist-all-thumb v2
func thumbOf(e *ytdlp.ExtractedInfo) string {
	return plAllThumbnail(e)
}
'''


def ensure_helper_file():
    path = PROJECT_ROOT / "services" / "playlist_all.go"
    if path.exists():
        content = read_text(path)
        if HELPER_MARKER in content:
            print("ALREADY APPLIED: services/playlist_all.go")
            return
        if "ytdlp-studio:playlist-all" in content:
            write_text(path, HELPER_GO)
            return
        fail(
            "services/playlist_all.go zaten mevcut ama beklenen script-owned marker yok.\n"
            "Dosya elle değiştirilmiş olabilir. Script güvenli şekilde devam edemiyor."
        )
    write_text(path, HELPER_GO)


def find_matching_brace(content: str, open_pos: int):
    depth = 0
    i = open_pos
    n = len(content)

    in_string = False
    in_rune = False
    in_raw = False
    in_line_comment = False
    in_block_comment = False

    while i < n:
        c = content[i]

        if in_line_comment:
            if c == "\n":
                in_line_comment = False
        elif in_block_comment:
            if c == "*" and i + 1 < n and content[i + 1] == "/":
                in_block_comment = False
                i += 1
        elif in_raw:
            if c == "`":
                in_raw = False
        elif in_string:
            if c == "\\":
                i += 1
            elif c == '"':
                in_string = False
        elif in_rune:
            if c == "\\":
                i += 1
            elif c == "'":
                in_rune = False
        else:
            if c == "/" and i + 1 < n:
                if content[i + 1] == "/":
                    in_line_comment = True
                    i += 1
                elif content[i + 1] == "*":
                    in_block_comment = True
                    i += 1
            elif c == "`":
                in_raw = True
            elif c == '"':
                in_string = True
            elif c == "'":
                in_rune = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return i
        i += 1

    return None


def strip_marker_lines(content: str, marker_base: str) -> str:
    lines = content.splitlines(keepends=True)
    pattern = re.compile(r"^\s*//" + re.escape(marker_base) + r" v\d+\s*$")
    return "".join(line for line in lines if not pattern.match(line.rstrip("\n")))


def replace_go_function(file_path: Path, func_pattern: str, new_func: str, marker: str, marker_base: str, desc: str):
    content = read_text(file_path)

    if marker in content:
        print(f"ALREADY APPLIED: {file_path.name} - {desc}")
        return

    content = strip_marker_lines(content, marker_base)

    match = re.search(func_pattern, content)
    if not match:
        fail(
            f"Beklenen Go fonksiyonu bulunamadı:\n"
            f"Dosya: {file_path}\n"
            f"İşlem: {desc}\n"
            f"Pattern: {func_pattern}"
        )

    brace_pos = content.find("{", match.end())
    if brace_pos == -1:
        fail(f"Fonksiyon gövdesi bulunamadı:\n{file_path}\n{desc}")

    end_pos = find_matching_brace(content, brace_pos)
    if end_pos is None:
        fail(f"Fonksiyon kapatma brace'i bulunamadı:\n{file_path}\n{desc}")

    new_content = content[:match.start()] + new_func.rstrip() + "\n" + content[end_pos + 1:]
    write_text(file_path, new_content)
    print(f"PATCHED: {file_path.name} - {desc}")


def patch_analyze_service():
    analyze_path = PROJECT_ROOT / "services" / "analyze.go"
    replace_go_function(
        analyze_path,
        r"func\s+\(\s*s\s+\*AnalyzeService\s*\)\s+Analyze\s*\(",
        NEW_ANALYZE_FUNC,
        ANALYZE_MARKER,
        "ytdlp-studio:playlist-all-analyze",
        "Analyze fonksiyonu tüm playlist entry'lerini listeleyecek şekilde güncellendi",
    )

    replace_go_function(
        analyze_path,
        r"func\s+thumbOf\s*\(",
        NEW_THUMB_FUNC,
        THUMB_MARKER,
        "ytdlp-studio:playlist-all-thumb",
        "thumbOf güvenli thumbnail helper'ına yönlendirildi",
    )


def ensure_regex_replace(file_path: Path, pattern: str, replacement: str, check_pattern: str, desc: str):
    content = read_text(file_path)

    if re.search(check_pattern, content):
        print(f"ALREADY APPLIED: {file_path.name} - {desc}")
        return

    if not re.search(pattern, content):
        fail(
            f"Beklenen içerik bulunamadı:\n"
            f"Dosya: {file_path}\n"
            f"İşlem: {desc}\n"
            f"Pattern: {pattern}"
        )

    new_content = re.sub(pattern, replacement, content, count=1)
    if new_content == content:
        fail(f"Regex replacement uygulanamadı:\n{file_path}\n{desc}")

    write_text(file_path, new_content)
    print(f"PATCHED: {file_path.name} - {desc}")


def patch_frontend_types():
    types_path = PROJECT_ROOT / "frontend" / "src" / "types.ts"

    ensure_regex_replace(
        types_path,
        r'kind:\s*"video"\s*\|\s*"playlist"\s*\|\s*"unknown"\s*;',
        "kind: string;",
        r"kind:\s*string\s*;",
        "ParsedURL.kind tipi generated binding'e uyarlandı",
    )

    ensure_regex_replace(
        types_path,
        r'mode:\s*"audio"\s*\|\s*"video"\s*;',
        "mode: string;",
        r"mode:\s*string\s*;",
        "DownloadOptions.mode tipi generated binding'e uyarlandı",
    )

    ensure_regex_replace(
        types_path,
        r'state:\s*"queued"\s*\|\s*"downloading"\s*\|\s*"converting"\s*\|\s*"done"\s*\|\s*"error"\s*\|\s*"canceled"\s*;',
        "state: string;",
        r"state:\s*string\s*;",
        "TaskProgress.state tipi generated binding'e uyarlandı",
    )

    ensure_regex_replace(
        types_path,
        r"missing:\s*string\[\]\s*;",
        "missing: string[] | null;",
        r"missing:\s*string\[\]\s*\|\s*null\s*;",
        "DepStatus.missing tipi null-safe hale getirildi",
    )

    ensure_regex_replace(
        types_path,
        r"entries:\s*MediaEntry\[\]\s*;",
        "entries: MediaEntry[] | null;",
        r"entries:\s*MediaEntry\[\]\s*\|\s*null\s*;",
        "MediaInfo.entries tipi null-safe hale getirildi",
    )


def patch_preview_list():
    path = PROJECT_ROOT / "frontend" / "src" / "components" / "PreviewList.tsx"
    content = read_text(path)
    changed = False

    if re.search(r"const entries = info\.entries \?\? \[\];", content):
        print("ALREADY APPLIED: PreviewList.tsx - entries null-safe filter")
    else:
        pattern = re.compile(
            r"([ \t]*)const visible = info\.entries\.filter\(\(e\) => e\.title\.toLowerCase\(\)\.includes\(filter\.toLowerCase\(\)\)\);"
        )
        match = pattern.search(content)
        if not match:
            fail(
                "Beklenen PreviewList filter satırı bulunamadı.\n"
                f"Dosya: {path}"
            )
        indent = match.group(1)
        replacement = (
            indent + "const entries = info.entries ?? [];\n"
            + indent + "const visible = entries.filter((e) => e.title.toLowerCase().includes(filter.toLowerCase()));"
        )
        content = content[:match.start()] + replacement + content[match.end():]
        changed = True
        print("PATCHED: PreviewList.tsx - entries null-safe filter")

    if re.search(r"\{selected\.size\}/\{entries\.length\}", content):
        print("ALREADY APPLIED: PreviewList.tsx - entries null-safe count")
    else:
        old_count = "{selected.size}/{info.entries.length}"
        new_count = "{selected.size}/{entries.length}"
        if old_count not in content:
            fail(
                "Beklenen PreviewList count satırı bulunamadı.\n"
                f"Dosya: {path}"
            )
        content = content.replace(old_count, new_count, 1)
        changed = True
        print("PATCHED: PreviewList.tsx - entries null-safe count")

    if changed:
        write_text(path, content)


def patch_paste_bar():
    path = PROJECT_ROOT / "frontend" / "src" / "components" / "PasteBar.tsx"
    content = read_text(path)

    has_info_fallback = re.search(r"info:\s*info\s*\?\?\s*undefined", content)
    has_entries_fallback = re.search(r"info\?\.entries\s*\?\?\s*\[\]", content)

    if has_info_fallback and has_entries_fallback:
        print("ALREADY APPLIED: PasteBar.tsx - info null-safe set")
        return

    pattern = re.compile(
        r"set\(\{\s*"
        r"url:\s*trimmed,\s*"
        r"parsed:\s*p,\s*"
        r"info,\s*"
        r"selected:\s*new Set\(info\.entries\.filter\(\(e\) => e\.available\)\.map\(\(e\) => e\.id\)\)\),?\s*"
        r"\}\);"
    )

    match = pattern.search(content)
    if not match:
        fail(
            "Beklenen PasteBar set() bloğu bulunamadı.\n"
            f"Dosya: {path}"
        )

    line_start = content.rfind("\n", 0, match.start()) + 1
    indent = content[line_start:match.start()]

    replacement = (
        indent + "set({\n"
        + indent + "  url: trimmed,\n"
        + indent + "  parsed: p,\n"
        + indent + "  info: info ?? undefined,\n"
        + indent + "  selected: new Set((info?.entries ?? []).filter((e) => e.available).map((e) => e.id)),\n"
        + indent + "});"
    )

    content = content[:match.start()] + replacement + content[match.end():]
    write_text(path, content)
    print("PATCHED: PasteBar.tsx - info null-safe set")


def validate():
    if not shutil.which("go"):
        fail("go komutu bulunamadı. Go kurulu olduğundan emin olun.")

    if not run_cmd(["go", "mod", "tidy"], cwd=PROJECT_ROOT):
        fail("go mod tidy başarısız oldu.")

    if not run_cmd(["go", "fmt", "./services"], cwd=PROJECT_ROOT):
        fail("go fmt ./services başarısız oldu.")

    if not run_cmd(["go", "build", "./..."], cwd=PROJECT_ROOT):
        fail("Go build başarısız oldu.")

    if not run_cmd(["go", "test", "./..."], cwd=PROJECT_ROOT):
        fail("Go testleri başarısız oldu.")

    if not shutil.which("npm"):
        fail("npm komutu bulunamadı. Node.js kurulu olduğundan emin olun.")

    frontend_dir = PROJECT_ROOT / "frontend"
    if not frontend_dir.exists():
        fail("frontend dizini bulunamadı.")

    if not (frontend_dir / "node_modules").exists():
        if not run_cmd(["npm", "install", "--no-audit", "--no-fund"], cwd=frontend_dir):
            fail("npm install başarısız oldu.")

    if not run_cmd(["npm", "run", "build:dev"], cwd=frontend_dir):
        fail("Frontend build başarısız oldu.")


def main():
    print("=== Applying full playlist listing changes ===")

    ensure_helper_file()
    patch_analyze_service()
    patch_frontend_types()
    patch_preview_list()
    patch_paste_bar()

    print("\n=== Validating ===")
    validate()

    print(
        """
=== UPDATE SUMMARY ===

Created:
- services/playlist_all.go

Modified:
- services/analyze.go
- frontend/src/types.ts
- frontend/src/components/PreviewList.tsx
- frontend/src/components/PasteBar.tsx

Behavior:
- Playlist analizinde tüm yt-dlp entry'leri flatten edilir.
- Duplicate entry'ler temizlenir.
- Playlist başlığı ve ID'si flat output senaryosunda korunur.
- Frontend tüm entry'leri null-safe şekilde listeler.

Validation:
- go mod tidy: PASS
- go fmt: PASS
- go build: PASS
- go test: PASS
- frontend build:dev: PASS

Completed successfully.
"""
    )

    print(
        """
=== GIT COMMIT MESSAGE ===

feat(analyze): list all playlist entries after analysis

- flatten and deduplicate all yt-dlp infos instead of using only the first result
- support both nested playlist output and flat per-entry output
- preserve playlist title and ID when flat playlist entries are returned
- add reflective metadata access helpers for go-ytdlp pointer fields
- harden frontend rendering against null MediaInfo.entries
"""
    )


if __name__ == "__main__":
    main()