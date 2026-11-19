import os
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
    print("ERROR: Could not find project root (missing go.mod or Taskfile.yml)")
    sys.exit(1)

print(f"Found project root at: {ROOT}")

def patch_file(rel_path, old_content, new_content, description):
    file_path = ROOT / rel_path
    if not file_path.exists():
        print(f"ERROR: File not found: {file_path} - {description}")
        sys.exit(1)
        
    content = file_path.read_text(encoding='utf-8')
    if old_content not in content:
        if new_content in content:
            print(f"ALREADY APPLIED: {file_path.name} - {description}")
            return
        print(f"ERROR: Expected old content not found in {file_path} for: {description}")
        print("--- Snippet of actual content ---")
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if any(word in line for word in old_content.split()[:3]):
                print('\n'.join(lines[max(0, i-2):i+5]))
                break
        print("----------------------------------")
        sys.exit(1)
        
    new_content_full = content.replace(old_content, new_content)
    if content == new_content_full:
         print(f"WARNING: No replacement made in {file_path} for: {description}")
         sys.exit(1)
         
    file_path.write_text(new_content_full, encoding='utf-8')
    print(f"PATCHED: {file_path.name} - {description}")

# 1. main.go - Wails v3 Window API update
old_main = """	app.NewWebviewWindowWithOptions(application.WebviewWindowOptions{
		Title:  "ytdlp-studio",
		Width:  1180,
		Height: 760,
		URL:    "/",
	})"""
new_main = """	app.Window.NewWithOptions(application.WebviewWindowOptions{
		Title:  "ytdlp-studio",
		Width:  1180,
		Height: 760,
		URL:    "/",
	})"""
patch_file("main.go", old_main, new_main, "Update Wails v3 window creation API")

# 2. services/analyze.go - Handle pointer fields for ExtractedInfo
old_analyze1 = """	info := infos[0]
	out := &model.MediaInfo{Kind: "video", ID: info.ID, Title: info.Title}"""
new_analyze1 = """	info := infos[0]
	title := ""
	if info.Title != nil {
		title = *info.Title
	}
	out := &model.MediaInfo{Kind: "video", ID: info.ID, Title: title}"""
patch_file("services/analyze.go", old_analyze1, new_analyze1, "Handle pointer Title in MediaInfo")

old_analyze2 = """		me := model.MediaEntry{
			ID:          e.ID,
			URL:         e.WebpageURL,
			Title:       e.Title,
			DurationSec: e.Duration,
			Index:       i + 1,
			Available:   e.Title != "[Private video]" && e.Title != "[Deleted video]",
		}"""
new_analyze2 = """		webpageURL := ""
		if e.WebpageURL != nil {
			webpageURL = *e.WebpageURL
		}
		titleStr := ""
		if e.Title != nil {
			titleStr = *e.Title
		}
		duration := 0.0
		if e.Duration != nil {
			duration = *e.Duration
		}
		available := true
		if e.Title != nil && (*e.Title == "[Private video]" || *e.Title == "[Deleted video]") {
			available = false
		}

		me := model.MediaEntry{
			ID:          e.ID,
			URL:         webpageURL,
			Title:       titleStr,
			DurationSec: duration,
			Index:       i + 1,
			Available:   available,
		}"""
patch_file("services/analyze.go", old_analyze2, new_analyze2, "Handle pointer fields in MediaEntry")

# 3. services/download.go - Update ProgressUpdate API
old_download = """		total := p.TotalBytes
		if total == 0 {
			total = p.TotalBytesEstimate
		}
		pct := 0.0
		if total > 0 {
			pct = float64(p.DownloadedBytes) / float64(total) * 100
		}
		state := "downloading"
		if string(p.Status) == "finished" {
			state = "converting"
			pct = 100
		}
		d.emit(TaskProgress{TaskID: t.id, State: state, Percent: pct, Speed: p.Speed, ETA: p.ETA.Seconds()})"""
new_download = """		total := p.TotalBytes
		pct := 0.0
		if total > 0 {
			pct = float64(p.DownloadedBytes) / float64(total) * 100
		}
		state := "downloading"
		if string(p.Status) == "finished" {
			state = "converting"
			pct = 100
		}
		
		eta := 0.0
		if p.ETA != nil {
			eta = p.ETA().Seconds()
		}
		
		d.emit(TaskProgress{TaskID: t.id, State: state, Percent: pct, Speed: 0, ETA: eta})"""
patch_file("services/download.go", old_download, new_download, "Update ProgressUpdate fields and methods")

# 4. frontend/src/types.ts - Relax types to match generated Wails bindings
old_types_mode = """  mode: "audio" | "video";"""
new_types_mode = """  mode: string;"""
patch_file("frontend/src/types.ts", old_types_mode, new_types_mode, "Relax DownloadOptions.mode type")

old_types_missing = """  missing: string[];"""
new_types_missing = """  missing: string[] | null;"""
patch_file("frontend/src/types.ts", old_types_missing, new_types_missing, "Relax DepStatus.missing type")

old_types_entries = """  entries: MediaEntry[];"""
new_types_entries = """  entries: MediaEntry[] | null;"""
patch_file("frontend/src/types.ts", old_types_entries, new_types_entries, "Relax MediaInfo.entries type")

old_parsed_url = """  kind: "video" | "playlist" | "unknown";"""
new_parsed_url = """  kind: string;"""
patch_file("frontend/src/types.ts", old_parsed_url, new_parsed_url, "Relax ParsedURL.kind type")

old_state = """  state: "queued" | "downloading" | "converting" | "done" | "error" | "canceled";"""
new_state = """  state: string;"""
patch_file("frontend/src/types.ts", old_state, new_state, "Relax TaskProgress.state type")

# 5. frontend/src/components/PasteBar.tsx - Handle null info.entries
old_pastebar = """      set({
        url: trimmed,
        parsed: p,
        info,
        selected: new Set(info.entries.filter((e) => e.available).map((e) => e.id)),
      });"""
new_pastebar = """       set({
         url: trimmed,
         parsed: p,
         info: info ?? undefined,
         selected: new Set((info?.entries ?? []).filter((e) => e.available).map((e) => e.id)),
       });"""
patch_file("frontend/src/components/PasteBar.tsx", old_pastebar, new_pastebar, "Handle null info and entries in PasteBar")

# 6. frontend/src/components/DownloadButton.tsx - Handle null ids
old_download_btn = """      const ids = await DownloadService.Enqueue(entries, options);
      addMany(ids, entries);"""
new_download_btn = """       const ids = await DownloadService.Enqueue(entries, options);
       addMany(ids ?? [], entries);"""
patch_file("frontend/src/components/DownloadButton.tsx", old_download_btn, new_download_btn, "Handle null ids in DownloadButton")

print("\n=== UPDATE SUMMARY ===")
print("Modified:")
print("- main.go: Wails v3 window creation API updated")
print("- services/analyze.go: Handled go-ytdlp pointer fields (*string, *float64)")
print("- services/download.go: Updated go-ytdlp ProgressUpdate API")
print("- frontend/src/types.ts: Relaxed types to match generated bindings")
print("- frontend/src/components/PasteBar.tsx: Handled null info.entries")
print("- frontend/src/components/DownloadButton.tsx: Handled null ids")
print("\nValidation:")
print("- Go build: `go build ./...` or `wails3 build`")
print("- TS build: `cd frontend && npm run build`")

print("\n=== GIT COMMIT MESSAGE ===")
print("""fix: resolve wails v3 and go-ytdlp api compatibility issues

- Update Wails v3 window creation from app.NewWebviewWindowWithOptions to app.Window.NewWithOptions
- Handle pointer fields (*string, *float64) introduced in recent go-ytdlp versions for ExtractedInfo
- Update ProgressUpdate API usage in download service (ETA is now a method, Speed removed)
- Relax TypeScript types to match Wails generated bindings (mode, missing, entries, kind, state)
- Add null-safety checks for info.entries and ids in React components
""")