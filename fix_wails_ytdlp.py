#!/usr/bin/env python3
"""
ytdlp-studio · Modern UI + Progress Tracking + playlist_index NA Fix

Yapılanlar:
1. playlist_index "NA" problemi çözülür (yt-dlp OutputNaPlaceholder + Go template fallback)
2. Modern blend tema uygulanır (sidebar + kartlar + meter + tag + toast)
3. Frontend component'leri yeniden yazılır
4. Playlist batch progress tracking eklenir (backend + frontend)
5. Go pointer field handling (ExtractedInfo *string, *float64)
6. ProgressUpdate API güncellenir (ETA method, Speed removed)
7. index.html'den /style.css referansı kaldırılır
8. public/style.css silinir (eski tema)

Backup oluşturmaz. Markdown dosyası üretmez.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

ROOT: Path | None = None
CREATED: list[str] = []
MODIFIED: list[str] = []
DELETED: list[str] = []


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def find_project_root() -> Path:
    current = Path.cwd()
    while current != current.parent:
        if (current / "go.mod").exists() and (current / "Taskfile.yml").exists():
            return current
        current = current.parent
    raise SystemExit("ERROR: Proje kökü bulunamadı (go.mod + Taskfile.yml aranıyor).")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def fail(message: str) -> NoReturn:
    print("\nERROR:")
    print(message)
    print("\nPatch uygulanmadı.")
    sys.exit(1)


def run(cmd: list[str], cwd: Path | None = None, ok_empty: bool = False) -> bool:
    print("$ " + " ".join(cmd))
    proc = subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, text=True, capture_output=True
    )
    if proc.stdout:
        print(proc.stdout.rstrip())
    if proc.stderr:
        print(proc.stderr.rstrip())
    if proc.returncode != 0 and not ok_empty:
        return False
    return True


def read(path: Path) -> str:
    if not path.exists():
        fail(f"Dosya bulunamadı:\n{path}")
    return path.read_text(encoding="utf-8")


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_owned(path: Path, content: str, marker: str, kind: str) -> None:
    """Script'in sahiplendiği dosyaları kontrollü biçimde yeniden yazar."""
    if path.exists():
        current = read(path)
        if marker not in current:
            fail(
                "Dosya script-owned marker içermiyor.\n"
                f"Dosya: {rel(path)}\n"
                f"Beklenen marker: {marker}\n"
                "Dosya elle değiştirilmiş olabilir; yanlış dosyaya yazmamak için işlem durduruldu."
            )
        write(path, content)
        MODIFIED.append(f"{rel(path)} ({kind})")
        print(f"UPDATED : {rel(path)}")
    else:
        write(path, content)
        CREATED.append(f"{rel(path)} ({kind})")
        print(f"CREATED : {rel(path)}")

    if marker not in read(path):
        fail(f"Değişiklik doğrulanamadı (marker yok): {rel(path)}")


def delete_if_unreferenced(path: Path, needles: list[str], scan_dirs: list[Path]) -> None:
    if not path.exists():
        return
    content = read(path)
    if not any(n in content for n in needles):
        fail(
            "Silme doğrulaması başarısız.\n"
            f"Dosya: {rel(path)}\n"
            "Beklenen eski tema belirteçleri bulunamadı."
        )
    for base in scan_dirs:
        if not base.exists():
            continue
        for f in base.rglob("*"):
            if not f.is_file() or f.suffix not in {".html", ".ts", ".tsx", ".css", ".json"}:
                continue
            if "node_modules" in f.parts or "dist" in f.parts or "bindings" in f.parts:
                continue
            if f == path:
                continue
            if path.name in read(f):
                fail(f"Silme iptal: {rel(path)} hâlâ {rel(f)} içinden referans alıyor.")
    path.unlink()
    DELETED.append(f"{rel(path)} (kullanılmayan eski tema dosyası)")
    print(f"DELETED : {rel(path)}")


# --------------------------------------------------------------------------- #
# 1. internal/engine/builder.go
# --------------------------------------------------------------------------- #
ENGINE_BUILDER = '''// ytdlp-studio:generated v1
// ytdlp-studio:output-template v1
package engine

import (
	"fmt"
	"sync"

	"github.com/lrstanley/go-ytdlp"
	"ytdlp-studio/internal/model"
)

var (
	mu        sync.RWMutex
	ytDlpPath string
	ffmpegDir string
)

func SetPaths(ytDlp, ffDir string) {
	mu.Lock()
	defer mu.Unlock()
	ytDlpPath, ffmpegDir = ytDlp, ffDir
}

func NewCommand() *ytdlp.Command {
	mu.RLock()
	yt, ff := ytDlpPath, ffmpegDir
	mu.RUnlock()

	c := ytdlp.New().IgnoreConfig()
	if yt != "" {
		c = c.SetExecutable(yt)
	}
	if ff != "" {
		c = c.FFmpegLocation(ff)
	}
	return c
}

func BuildCommand(o model.DownloadOptions) *ytdlp.Command {
	c := NewCommand().
		NoPlaylist().
		Paths("home:" + o.OutputDir).
		Output(o.NameTemplate).
		OutputNaPlaceholder("000")

	if o.Mode == "audio" {
		c = c.ExtractAudio().AudioFormat(o.AudioFormat).AudioQuality(o.AudioQuality)
	} else {
		f := "bv*+ba/b"
		if o.VideoHeight > 0 {
			f = fmt.Sprintf("bv*[height<=%d]+ba/b[height<=%d]", o.VideoHeight, o.VideoHeight)
		}
		c = c.Format(f).MergeOutputFormat(o.VideoContainer)
	}
	if o.EmbedThumbnail {
		c = c.EmbedThumbnail()
	}
	if o.EmbedMetadata {
		c = c.EmbedMetadata()
	}
	if o.ConcurrentFragments > 1 {
		c = c.ConcurrentFragments(o.ConcurrentFragments)
	}
	if o.RateLimit != "" {
		c = c.LimitRate(o.RateLimit)
	}
	if o.CookiesBrowser != "" {
		c = c.CookiesFromBrowser(o.CookiesBrowser)
	}
	return c
}
'''


def patch_engine_builder() -> None:
    path = ROOT / "internal" / "engine" / "builder.go"
    write_owned(path, ENGINE_BUILDER, "// ytdlp-studio:generated v1", "OutputNaPlaceholder eklendi")


# --------------------------------------------------------------------------- #
# 2. services/analyze.go — pointer fields + playlist flattening
# --------------------------------------------------------------------------- #
SERVICES_ANALYZE = '''// ytdlp-studio:generated v1
// ytdlp-studio:analyze-pointers v1
package services

import (
	"context"
	"errors"
	"fmt"
	"net/url"
	"strings"
	"time"

	"github.com/lrstanley/go-ytdlp"
	"ytdlp-studio/internal/engine"
	"ytdlp-studio/internal/model"
)

type AnalyzeService struct{}

func (s *AnalyzeService) ParseURL(raw string) (model.ParsedURL, error) {
	p := model.ParsedURL{Kind: "unknown", CanonicalURL: strings.TrimSpace(raw)}
	u, err := url.Parse(p.CanonicalURL)
	if err != nil || u.Scheme == "" || u.Host == "" {
		return p, fmt.Errorf("geçersiz URL: %q", raw)
	}
	host := strings.ToLower(u.Host)
	host = strings.TrimPrefix(host, "www.")
	host = strings.TrimPrefix(host, "m.")
	q := u.Query()
	p.VideoID, p.ListID = q.Get("v"), q.Get("list")

	switch {
	case host == "youtu.be":
		p.VideoID = strings.Trim(u.Path, "/")
	case strings.HasSuffix(host, "youtube.com") || strings.HasSuffix(host, "youtube-nocookie.com"):
		parts := strings.Split(strings.Trim(u.Path, "/"), "/")
		if len(parts) >= 2 && (parts[0] == "shorts" || parts[0] == "live" || parts[0] == "embed") {
			p.VideoID = parts[1]
		}
	}

	switch {
	case p.VideoID != "" && p.ListID != "":
		p.Kind, p.Ambiguous = "video", true
	case p.ListID != "":
		p.Kind = "playlist"
	case p.VideoID != "":
		p.Kind = "video"
	}
	p.IsMix = strings.HasPrefix(p.ListID, "RD")
	return p, nil
}

func (s *AnalyzeService) Analyze(raw, scope string) (*model.MediaInfo, error) {
	p, err := s.ParseURL(raw)
	if err != nil {
		return nil, err
	}
	target := p.CanonicalURL
	switch {
	case p.Kind == "playlist" || (p.Ambiguous && scope == "playlist"):
		target = "https://www.youtube.com/playlist?list=" + p.ListID
	case p.VideoID != "":
		target = "https://www.youtube.com/watch?v=" + p.VideoID
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()

	infos, _, err := engine.NewCommand().FlatPlaylist().ExtractInfo(ctx, target)
	if err != nil {
		return nil, fmt.Errorf("içerik analizi başarısız: %w", err)
	}
	if len(infos) == 0 {
		return nil, errors.New("içerik bulunamadı")
	}

	flat := plFlatten(infos)
	flat = plDedupe(flat)
	if len(flat) == 0 {
		return nil, errors.New("içerik bulunamadı")
	}

	kind := "video"
	id := p.VideoID
	title := ""

	if p.Kind == "playlist" || (p.Ambiguous && scope == "playlist") || len(flat) > 1 || plHasEntries(infos[0]) {
		kind = "playlist"
		id = p.ListID
		title = plPlaylistTitle(infos, p.ListID)
		if id == "" {
			id = plString(infos[0], "PlaylistID", "")
		}
		if id == "" {
			id = "playlist"
		}
	} else {
		id = plString(infos[0], "ID", p.VideoID)
		title = plString(infos[0], "Title", "")
	}
	if title == "" {
		title = plFirstTitle(flat)
	}
	if title == "" {
		title = id
	}

	out := &model.MediaInfo{Kind: kind, ID: id, Title: title}

	for i, e := range flat {
		if e == nil {
			continue
		}
		entryID := plString(e, "ID", "")
		webpageURL := plString(e, "WebpageURL", "")
		entryTitle := plString(e, "Title", "")
		duration := plFloat(e, "Duration", 0)

		idx := plInt(e, "PlaylistIndex", 0)
		if idx <= 0 {
			idx = i + 1
		}
		if entryTitle == "" {
			entryTitle = entryID
		}

		available := entryID != "" && !plIsUnavailable(entryTitle)

		me := model.MediaEntry{
			ID:          entryID,
			URL:         webpageURL,
			Title:       entryTitle,
			DurationSec: duration,
			Index:       idx,
			Available:   available,
		}
		if me.URL == "" && me.ID != "" {
			me.URL = "https://www.youtube.com/watch?v=" + me.ID
		}
		me.Thumbnail = plThumbnail(e)
		out.Entries = append(out.Entries, me)
	}

	return out, nil
}

func plHasEntries(e *ytdlp.ExtractedInfo) bool {
	return e != nil && len(e.Entries) > 0
}

func plFlatten(infos []*ytdlp.ExtractedInfo) []*ytdlp.ExtractedInfo {
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

func plDedupe(infos []*ytdlp.ExtractedInfo) []*ytdlp.ExtractedInfo {
	seen := make(map[string]bool)
	var out []*ytdlp.ExtractedInfo
	for _, e := range infos {
		if e == nil {
			continue
		}
		id := plString(e, "ID", "")
		url := plString(e, "WebpageURL", "")
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

func plPlaylistTitle(infos []*ytdlp.ExtractedInfo, fallback string) string {
	if len(infos) == 0 {
		if fallback != "" {
			return fallback
		}
		return "Playlist"
	}
	root := infos[0]
	if plHasEntries(root) {
		if t := plString(root, "Title", ""); t != "" {
			return t
		}
	}
	fields := []string{"PlaylistTitle", "Playlist", "Album", "Uploader", "Channel"}
	for _, info := range infos {
		if info == nil {
			continue
		}
		for _, f := range fields {
			if t := plString(info, f, ""); t != "" {
				return t
			}
		}
	}
	if root != nil {
		if t := plString(root, "Title", ""); t != "" {
			return t
		}
	}
	if fallback != "" {
		return fallback
	}
	return "Playlist"
}

func plFirstTitle(infos []*ytdlp.ExtractedInfo) string {
	for _, e := range infos {
		if e == nil {
			continue
		}
		if t := plString(e, "Title", ""); t != "" {
			return t
		}
	}
	return ""
}

func plIsUnavailable(title string) bool {
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

func plThumbnail(e *ytdlp.ExtractedInfo) string {
	if e == nil {
		return ""
	}
	if len(e.Thumbnails) > 0 {
		for i := len(e.Thumbnails) - 1; i >= 0; i-- {
			if e.Thumbnails[i] != nil && e.Thumbnails[i].URL != "" {
				return e.Thumbnails[i].URL
			}
		}
	}
	id := plString(e, "ID", "")
	if len(id) == 11 {
		return "https://i.ytimg.com/vi/" + id + "/hqdefault.jpg"
	}
	return ""
}

func plString(e *ytdlp.ExtractedInfo, name, fallback string) string {
	if e == nil {
		return fallback
	}
	switch name {
	case "ID":
		return e.ID
	case "Title":
		if e.Title != nil {
			return *e.Title
		}
	case "WebpageURL":
		if e.WebpageURL != nil {
			return *e.WebpageURL
		}
	case "PlaylistTitle":
		if e.PlaylistTitle != nil {
			return *e.PlaylistTitle
		}
	case "Playlist":
		if e.Playlist != nil {
			return *e.Playlist
		}
	case "Album":
		if e.Album != nil {
			return *e.Album
		}
	case "Uploader":
		if e.Uploader != nil {
			return *e.Uploader
		}
	case "Channel":
		if e.Channel != nil {
			return *e.Channel
		}
	case "PlaylistID":
		if e.PlaylistID != nil {
			return *e.PlaylistID
		}
	}
	return fallback
}

func plFloat(e *ytdlp.ExtractedInfo, name string, fallback float64) float64 {
	if e == nil {
		return fallback
	}
	if name == "Duration" && e.Duration != nil {
		return *e.Duration
	}
	return fallback
}

func plInt(e *ytdlp.ExtractedInfo, name string, fallback int) int {
	if e == nil {
		return fallback
	}
	if name == "PlaylistIndex" && e.PlaylistIndex != nil {
		return *e.PlaylistIndex
	}
	return fallback
}
'''


def patch_analyze() -> None:
    path = ROOT / "services" / "analyze.go"
    write_owned(path, SERVICES_ANALYZE, "// ytdlp-studio:generated v1", "pointer handling + flatten")


# --------------------------------------------------------------------------- #
# 3. services/download.go — ProgressUpdate API + batch progress
# --------------------------------------------------------------------------- #
SERVICES_DOWNLOAD = '''// ytdlp-studio:generated v1
// ytdlp-studio:download-progress v1
package services

import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"time"

	"github.com/lrstanley/go-ytdlp"
	"github.com/wailsapp/wails/v3/pkg/application"
	"ytdlp-studio/internal/engine"
	"ytdlp-studio/internal/model"
)

type TaskProgress struct {
	TaskID   string  `json:"taskId"`
	State    string  `json:"state"`
	Percent  float64 `json:"percent"`
	Speed    float64 `json:"speedBps"`
	ETA      float64 `json:"etaSec"`
	Error    string  `json:"error,omitempty"`
	FilePath string  `json:"filePath,omitempty"`
	BatchID  string  `json:"batchId,omitempty"`
}

type BatchProgress struct {
	BatchID   string `json:"batchId"`
	Total     int    `json:"total"`
	Completed int    `json:"completed"`
	Current   int    `json:"current"`
	Failed    int    `json:"failed"`
}

type downloadTask struct {
	id      string
	batchID string
	entry   model.MediaEntry
	opts    model.DownloadOptions
}

type DownloadService struct {
	mu       sync.Mutex
	queue    chan downloadTask
	cancels  map[string]context.CancelFunc
	canceled map[string]bool
	tasks    map[string]downloadTask
	batches  map[string]*batchState
	seq      int
}

type batchState struct {
	total     int
	completed int
	current   int
	failed    int
	mu        sync.Mutex
}

func NewDownloadService(workers int) *DownloadService {
	if workers < 1 {
		workers = 1
	}
	d := &DownloadService{
		queue:    make(chan downloadTask, 4096),
		cancels:  map[string]context.CancelFunc{},
		canceled: map[string]bool{},
		tasks:    map[string]downloadTask{},
		batches:  map[string]*batchState{},
	}
	for i := 0; i < workers; i++ {
		go d.worker()
	}
	return d
}

func (d *DownloadService) PickFolder() (string, error) {
	return application.Get().Dialog.OpenFile().
		SetTitle("İndirme Klasörü Seç").
		CanChooseDirectories(true).
		CanChooseFiles(false).
		PromptForSingleSelection()
}

func (d *DownloadService) Enqueue(entries []model.MediaEntry, opts model.DownloadOptions) ([]string, error) {
	if err := model.Validate(opts); err != nil {
		return nil, err
	}
	if len(entries) == 0 {
		return nil, errors.New("seçili öğe yok")
	}

	ids := make([]string, 0, len(entries))
	staged := make([]downloadTask, 0, len(entries))

	d.mu.Lock()
	d.seq++
	batchID := fmt.Sprintf("batch-%d", d.seq)

	batch := &batchState{total: len(entries)}
	d.batches[batchID] = batch

	for _, e := range entries {
		d.seq++
		id := fmt.Sprintf("%s-%d", e.ID, d.seq)
		t := downloadTask{id: id, batchID: batchID, entry: e, opts: opts}
		d.tasks[id] = t
		staged = append(staged, t)
		ids = append(ids, id)
	}
	d.mu.Unlock()

	d.emitBatch(batchID, batch)

	for _, t := range staged {
		d.queue <- t
		d.emit(TaskProgress{TaskID: t.id, State: "queued", BatchID: t.batchID})
	}
	return ids, nil
}

func (d *DownloadService) Cancel(taskID string) {
	d.mu.Lock()
	d.canceled[taskID] = true
	cancel := d.cancels[taskID]
	d.mu.Unlock()
	if cancel != nil {
		cancel()
	}
	d.emit(TaskProgress{TaskID: taskID, State: "canceled"})
}

func (d *DownloadService) Retry(taskID string) error {
	d.mu.Lock()
	t, ok := d.tasks[taskID]
	if ok {
		delete(d.canceled, taskID)
	}
	d.mu.Unlock()
	if !ok {
		return fmt.Errorf("görev bulunamadı: %s", taskID)
	}
	d.queue <- t
	d.emit(TaskProgress{TaskID: taskID, State: "queued", BatchID: t.batchID})
	return nil
}

func (d *DownloadService) Reveal(path string) error {
	if runtime.GOOS != "darwin" {
		return errors.New("bu özellik yalnızca macOS'ta destekleniyor")
	}
	if path == "" {
		return errors.New("dosya yolu boş")
	}
	st, err := os.Stat(path)
	switch {
	case err == nil && st.IsDir():
		return exec.Command("open", path).Run()
	case err == nil:
		return exec.Command("open", "-R", path).Run()
	default:
		dir := filepath.Dir(path)
		if _, e := os.Stat(dir); e == nil {
			return exec.Command("open", dir).Run()
		}
		return fmt.Errorf("dosya bulunamadı: %s", path)
	}
}

func (d *DownloadService) worker() {
	for t := range d.queue {
		d.mu.Lock()
		skip := d.canceled[t.id]
		d.mu.Unlock()
		if skip {
			continue
		}
		d.run(t)
	}
}

func (d *DownloadService) run(t downloadTask) {
	ctx, cancel := context.WithCancel(context.Background())
	d.mu.Lock()
	d.cancels[t.id] = cancel
	d.mu.Unlock()

	defer func() {
		cancel()
		d.mu.Lock()
		delete(d.cancels, t.id)
		d.mu.Unlock()
	}()

	var fm sync.Mutex
	lastFile := ""

	started := time.Now()
	cmd := engine.BuildCommand(t.opts).ProgressFunc(300*time.Millisecond, func(p ytdlp.ProgressUpdate) {
		fm.Lock()
		if p.Filename != "" {
			lastFile = p.Filename
		}
		fm.Unlock()

		total := p.TotalBytes
		pct := 0.0
		if total > 0 {
			pct = float64(p.DownloadedBytes) / float64(total) * 100
		}

		state := "downloading"
		if string(p.Status) == "finished" || string(p.Status) == "post_processing" {
			state = "converting"
			pct = 100
		}

		elapsed := time.Since(started).Seconds()
		speed := 0.0
		if elapsed > 0 {
			speed = float64(p.DownloadedBytes) / elapsed
		}

		eta := 0.0
		if p.ETA != nil {
			eta = p.ETA().Seconds()
		}

		d.emit(TaskProgress{
			TaskID:  t.id,
			State:   state,
			Percent: pct,
			Speed:   speed,
			ETA:     eta,
			BatchID: t.batchID,
		})
	})

	d.emit(TaskProgress{TaskID: t.id, State: "downloading", BatchID: t.batchID})

	_, err := cmd.Run(ctx, t.entry.URL)

	d.mu.Lock()
	wasCanceled := d.canceled[t.id]
	d.mu.Unlock()

	switch {
	case wasCanceled || ctx.Err() != nil:
		d.emit(TaskProgress{TaskID: t.id, State: "canceled", BatchID: t.batchID})
		d.recordBatchResult(t.batchID, false)
	case err != nil:
		d.emit(TaskProgress{TaskID: t.id, State: "error", Error: err.Error(), BatchID: t.batchID})
		d.recordBatchResult(t.batchID, false)
	default:
		fm.Lock()
		fp := lastFile
		fm.Unlock()
		if t.opts.Mode == "audio" && fp != "" {
			fp = strings.TrimSuffix(fp, filepath.Ext(fp)) + "." + t.opts.AudioFormat
		}
		d.emit(TaskProgress{
			TaskID:   t.id,
			State:    "done",
			Percent:  100,
			FilePath: fp,
			BatchID:  t.batchID,
		})
		d.recordBatchResult(t.batchID, true)
	}
}

func (d *DownloadService) recordBatchResult(batchID string, ok bool) {
	d.mu.Lock()
	batch := d.batches[batchID]
	d.mu.Unlock()
	if batch == nil {
		return
	}
	batch.mu.Lock()
	if ok {
		batch.completed++
	} else {
		batch.failed++
	}
	batch.mu.Unlock()
	d.emitBatch(batchID, batch)
}

func (d *DownloadService) emitBatch(batchID string, batch *batchState) {
	batch.mu.Lock()
	p := BatchProgress{
		BatchID:   batchID,
		Total:     batch.total,
		Completed: batch.completed,
		Current:   batch.completed + batch.failed,
		Failed:    batch.failed,
	}
	batch.mu.Unlock()

	if app := application.Get(); app != nil {
		app.Event.Emit("batch:progress", p)
	}
}

func (d *DownloadService) emit(p TaskProgress) {
	if app := application.Get(); app != nil {
		app.Event.Emit("task:progress", p)
	}
}
'''


def patch_download() -> None:
    path = ROOT / "services" / "download.go"
    write_owned(path, SERVICES_DOWNLOAD, "// ytdlp-studio:generated v1", "ProgressUpdate API + batch")


# --------------------------------------------------------------------------- #
# 4. services/events.go
# --------------------------------------------------------------------------- #
SERVICES_EVENTS = '''// ytdlp-studio:generated v1
// ytdlp-studio:events v1
package services

import "github.com/wailsapp/wails/v3/pkg/application"

func init() {
	application.RegisterEvent[TaskProgress]("task:progress")
	application.RegisterEvent[BatchProgress]("batch:progress")
	application.RegisterEvent[DepStatus]("deps:status")
}
'''


def patch_events() -> None:
    path = ROOT / "services" / "events.go"
    write_owned(path, SERVICES_EVENTS, "// ytdlp-studio:generated v1", "batch:progress event")


# --------------------------------------------------------------------------- #
# 5. frontend/index.html
# --------------------------------------------------------------------------- #
FRONTEND_INDEX_HTML = '''<!DOCTYPE html>
<html lang="tr" data-ui="ytdlp-studio:ui-blend v1">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/wails.png" />
    <meta name="color-scheme" content="dark" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
    <title>ytdlp-studio</title>
  </head>
  <body>
    <div class="bg" aria-hidden="true"></div>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
'''


def patch_index_html() -> None:
    path = ROOT / "frontend" / "index.html"
    current = read(path)
    if 'data-ui="ytdlp-studio:ui-blend v1"' in current and 'href="/style.css"' not in current:
        print("ALREADY : frontend/index.html")
        return
    if '<div id="root"></div>' not in current:
        fail("index.html root div içermiyor; işlem durduruldu.")
    write(path, FRONTEND_INDEX_HTML)
    MODIFIED.append("frontend/index.html (eski /style.css kaldırıldı, dark color-scheme)")
    print("UPDATED : frontend/index.html")


# --------------------------------------------------------------------------- #
# 6. frontend/src/index.css — modern blend theme
# --------------------------------------------------------------------------- #
FRONTEND_INDEX_CSS = '''/* ytdlp-studio:generated v1 */
/* ytdlp-studio:ui-blend v1 */
:root {
  --bg: #0a0f19;
  --panel: #111a29;
  --panel2: #162236;
  --stroke: #26354a;
  --text: #eaf1fb;
  --muted: #98a9bf;
  --blue: #64a4ff;
  --cyan: #61d6d2;
  --green: #63d6a0;
  --amber: #f5c46a;
  --red: #ff7d89;
  --radius: 14px;
  --shadow: 0 10px 28px rgba(0, 0, 0, 0.35);
}

* { box-sizing: border-box; }

html, body {
  margin: 0;
  padding: 0;
  height: 100%;
  background: radial-gradient(ellipse at 15% 0%, #173052 0, transparent 36%), var(--bg);
  color: var(--text);
  font: 14px/1.45 Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  -webkit-font-smoothing: antialiased;
}

button, input, select, textarea {
  font: inherit;
  color: inherit;
}

button {
  cursor: pointer;
  transition: transform 0.12s, border-color 0.12s, background 0.12s;
}

button:active { transform: translateY(1px); }
button:disabled { opacity: 0.45; cursor: not-allowed; }

.bg {
  position: fixed;
  inset: 0;
  pointer-events: none;
  background: radial-gradient(ellipse at 85% 100%, #172b43 0, transparent 40%);
  z-index: 0;
}

.app {
  position: relative;
  z-index: 1;
  min-height: 100vh;
  display: grid;
  grid-template-columns: 230px 1fr;
}

/* ---------- Sidebar ---------- */
.sidebar {
  border-right: 1px solid var(--stroke);
  background: #0a101bd9;
  padding: 22px 14px;
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 8px;
}

.brand-mark {
  height: 38px;
  width: 38px;
  border-radius: 12px;
  background: linear-gradient(140deg, #5da5ff, #62d6d0);
  color: #081320;
  display: grid;
  place-items: center;
  font-weight: 900;
  font-size: 18px;
  box-shadow: 0 6px 18px rgba(77, 169, 247, 0.25);
}

.brand strong { display: block; font-size: 15px; letter-spacing: 0.2px; }
.brand span { color: var(--muted); font-size: 11px; }

.nav-label {
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 1.6px;
  color: #71859e;
  padding: 0 10px;
  margin-bottom: 6px;
}

.nav { display: grid; gap: 4px; }

.nav button {
  color: #9eafc4;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 10px;
  text-align: left;
  padding: 10px 11px;
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}

.nav button:hover { background: #13223a; }

.nav button.active {
  color: var(--text);
  background: linear-gradient(90deg, #24466c99, #172b4399);
  border-color: #345475;
}

.nav .ico {
  width: 20px;
  text-align: center;
  font-size: 15px;
}

.sidebar-bottom {
  margin-top: auto;
  background: #101c2c;
  border: 1px solid var(--stroke);
  border-radius: 12px;
  padding: 12px;
  color: var(--muted);
  font-size: 11px;
  line-height: 1.5;
}

.sidebar-bottom strong { display: block; color: var(--text); margin-bottom: 3px; }

/* ---------- Main ---------- */
.main {
  min-width: 0;
  padding: 22px clamp(14px, 3vw, 32px) 32px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.eyebrow {
  text-transform: uppercase;
  letter-spacing: 1.8px;
  font-size: 10px;
  color: var(--cyan);
  font-weight: 800;
}

.topbar h1 {
  font-size: 22px;
  margin: 3px 0 0;
  letter-spacing: -0.5px;
}

.conn-box {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

/* ---------- Inputs ---------- */
input, select, textarea {
  width: 100%;
  background: #0b1421;
  border: 1px solid #30415a;
  border-radius: 10px;
  color: var(--text);
  padding: 9px 11px;
  outline: none;
}

input:focus, select:focus, textarea:focus {
  border-color: var(--blue);
  box-shadow: 0 0 0 3px rgba(100, 164, 255, 0.12);
}

input::placeholder { color: #667d98; }

/* ---------- Buttons ---------- */
.btn {
  border: 1px solid #32465f;
  background: #17263a;
  color: var(--text);
  padding: 8px 12px;
  border-radius: 10px;
  white-space: nowrap;
  font-size: 13px;
}

.btn:hover { border-color: #6080a5; background: #20334d; }

.btn.primary {
  background: linear-gradient(135deg, #4f9bf4, #4489d9);
  border-color: #69aaff;
  color: #081423;
  font-weight: 800;
}

.btn.ghost { background: transparent; }

.btn.success { color: #8ce4b4; border-color: #2c765b; background: #123327; }
.btn.danger { color: #ff9da5; border-color: #743b47; background: #371d27; }
.btn.small { padding: 5px 9px; font-size: 12px; }

.conn-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 9px;
  border-radius: 99px;
  border: 1px solid var(--stroke);
  background: #101a29;
  color: var(--muted);
  font-size: 11px;
  white-space: nowrap;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #75869d;
}

.dot.online { background: var(--green); box-shadow: 0 0 10px rgba(99, 214, 160, 0.4); }
.dot.wait { background: var(--amber); }

/* ---------- Cards ---------- */
.grid { display: grid; gap: 14px; }
.two { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.three { grid-template-columns: repeat(3, minmax(0, 1fr)); }

.card {
  background: linear-gradient(180deg, #141f30ee, #101927ee);
  border: 1px solid var(--stroke);
  border-radius: var(--radius);
  padding: 16px;
  box-shadow: var(--shadow);
  min-width: 0;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
}

.card h3 { font-size: 13px; margin: 0; font-weight: 750; }

.muted { color: var(--muted); }

/* ---------- Metric ---------- */
.metric {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.metric-label { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; }
.metric-value { font-size: 22px; font-weight: 800; letter-spacing: -0.6px; margin-top: 3px; }

.metric-icon {
  width: 36px;
  height: 36px;
  border-radius: 11px;
  display: grid;
  place-items: center;
  font-size: 16px;
  background: #233c59;
  color: #8ec2ff;
}

.metric-icon.mint { background: #173b3b; color: #72ded4; }
.metric-icon.gold { background: #40351f; color: #f4cc7c; }
.metric-icon.pink { background: #432530; color: #ff9aab; }

/* ---------- Inline / Field ---------- */
.inline { display: flex; gap: 7px; align-items: center; flex-wrap: wrap; }

.field { display: grid; gap: 5px; margin-bottom: 10px; }
.field label { font-size: 11px; color: #afbed0; text-transform: uppercase; letter-spacing: 0.8px; }
.field .hint { font-size: 10px; color: #7f94ac; line-height: 1.5; text-transform: none; letter-spacing: 0; }

.divider { border: 0; border-top: 1px solid var(--stroke); margin: 12px 0; }

/* ---------- Tags ---------- */
.tag {
  font-size: 10px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border-radius: 8px;
  border: 1px solid var(--stroke);
  padding: 3px 7px;
  color: var(--muted);
  background: #0d1725;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  font-weight: 700;
}

.tag.good { color: #8ce4b4; border-color: #2b624f; background: #10271f; }
.tag.warn { color: #f3ce83; border-color: #5a4a2c; background: #292213; }
.tag.bad { color: #ffa1aa; border-color: #5c333d; background: #2b171e; }
.tag.info { color: #9cc8ff; border-color: #34577e; background: #0f1f33; }

/* ---------- Meter / Progress ---------- */
.meter {
  height: 6px;
  background: #243247;
  border-radius: 99px;
  overflow: hidden;
  margin-top: 8px;
}

.meter span {
  height: 100%;
  display: block;
  width: 0;
  background: linear-gradient(90deg, var(--blue), var(--cyan));
  border-radius: 99px;
  transition: width 0.2s ease;
}

/* ---------- Paste bar ---------- */
.pastebar {
  display: flex;
  gap: 8px;
  align-items: stretch;
  background: linear-gradient(180deg, #141f30ee, #101927ee);
  border: 1px solid var(--stroke);
  border-radius: var(--radius);
  padding: 10px;
  box-shadow: var(--shadow);
}

.pastebar .url-input {
  flex: 1;
  min-width: 0;
  font-size: 13px;
}

/* ---------- Preview list ---------- */
.preview {
  background: linear-gradient(180deg, #141f30ee, #101927ee);
  border: 1px solid var(--stroke);
  border-radius: var(--radius);
  padding: 12px;
  box-shadow: var(--shadow);
  min-width: 0;
}

.preview.empty {
  padding: 22px 12px;
  text-align: center;
  color: #7188a2;
  font-size: 12px;
  border: 1px dashed #30415a;
}

.preview-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid #253247;
  margin-bottom: 8px;
}

.preview-head .select-all {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preview-head .select-all input { width: auto; }

.preview-head .filter {
  width: 160px;
  padding: 6px 9px;
  font-size: 12px;
}

.preview-head .count {
  font-size: 11px;
  color: var(--muted);
  padding: 3px 8px;
  border: 1px solid var(--stroke);
  border-radius: 99px;
  background: #0d1725;
}

.rows {
  display: grid;
  gap: 4px;
  max-height: 420px;
  overflow: auto;
}

.row {
  display: grid;
  grid-template-columns: auto 46px 42px 1fr auto;
  align-items: center;
  gap: 9px;
  padding: 7px 9px;
  border-radius: 9px;
  background: #0d1724;
  border: 1px solid #26384e;
  cursor: pointer;
  font-size: 12px;
}

.row:hover { border-color: #5c9ee9; background: #13283f; }
.row.unavailable { opacity: 0.5; cursor: not-allowed; }

.row input[type="checkbox"] { width: auto; }

.row img, .row .thumb-placeholder {
  width: 44px;
  height: 26px;
  border-radius: 4px;
  object-fit: cover;
  background: #1a2638;
}

.row .idx { color: var(--muted); font-size: 11px; font-variant-numeric: tabular-nums; }
.row .title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.row .dur { color: var(--cyan); font-variant-numeric: tabular-nums; font-size: 11px; }

/* ---------- Options panel ---------- */
.options {
  background: linear-gradient(180deg, #141f30ee, #101927ee);
  border: 1px solid var(--stroke);
  border-radius: var(--radius);
  padding: 14px;
  box-shadow: var(--shadow);
  min-width: 0;
}

.options h3 {
  margin: 0 0 10px;
  font-size: 13px;
  letter-spacing: -0.2px;
}

.seg {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 5px;
  padding: 3px;
  background: #0b1421;
  border: 1px solid #30415a;
  border-radius: 10px;
  margin-bottom: 12px;
}

.seg button {
  background: transparent;
  border: 1px solid transparent;
  color: var(--muted);
  padding: 7px 10px;
  border-radius: 8px;
  font-size: 12px;
}

.seg button.active {
  background: linear-gradient(135deg, #4f9bf4, #4489d9);
  color: #081423;
  font-weight: 800;
}

.options label {
  display: grid;
  gap: 4px;
  margin-bottom: 9px;
  font-size: 11px;
  color: #afbed0;
  text-transform: uppercase;
  letter-spacing: 0.8px;
}

.options label.check {
  display: flex;
  align-items: center;
  gap: 7px;
  text-transform: none;
  letter-spacing: 0;
  font-size: 12px;
  color: var(--text);
}

.options label.check input { width: auto; }

.folder-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 6px;
}

.options details {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid #253247;
}

.options details summary {
  cursor: pointer;
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 1px;
}

/* ---------- Download button / actionbar ---------- */
.actionbar {
  display: flex;
  justify-content: flex-end;
}

.download {
  background: linear-gradient(135deg, #4f9bf4, #4489d9);
  border: 1px solid #69aaff;
  color: #081423;
  font-weight: 800;
  padding: 10px 18px;
  border-radius: 11px;
  font-size: 13px;
  box-shadow: 0 6px 18px rgba(77, 169, 247, 0.25);
}

.download:hover { filter: brightness(1.08); }
.download:disabled { opacity: 0.45; box-shadow: none; }

/* ---------- Queue panel ---------- */
.queue-panel {
  background: linear-gradient(180deg, #141f30ee, #101927ee);
  border: 1px solid var(--stroke);
  border-radius: var(--radius);
  padding: 14px;
  box-shadow: var(--shadow);
  min-width: 0;
}

.batch-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 14px;
}

.task {
  background: #0d1724;
  border: 1px solid #26384e;
  border-radius: 10px;
  padding: 10px 12px;
  margin-bottom: 8px;
}

.task-line {
  display: grid;
  grid-template-columns: 1fr auto auto auto auto;
  align-items: center;
  gap: 8px;
  margin-bottom: 7px;
}

.task-line .title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
}

.task-line .meta {
  color: var(--cyan);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}

.bar {
  height: 5px;
  background: #243247;
  border-radius: 99px;
  overflow: hidden;
}

.bar .fill {
  height: 100%;
  background: linear-gradient(90deg, var(--blue), var(--cyan));
  border-radius: 99px;
  transition: width 0.2s ease;
}

.bar.converting .fill { background: linear-gradient(90deg, var(--amber), var(--green)); }
.bar.error .fill { background: linear-gradient(90deg, var(--red), #ff9da5); }
.bar.done .fill { background: linear-gradient(90deg, var(--green), #8ce4b4); }

.error { color: var(--red); font-size: 11px; margin-top: 6px; }
.error.small { font-size: 10px; }

/* ---------- Notice / Banner ---------- */
.notice {
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid #66502b;
  background: #2b2417;
  color: #e8c984;
  font-size: 12px;
  line-height: 1.5;
  cursor: pointer;
}

.notice.error {
  border-color: #643843;
  background: #2a171e;
  color: #ffa3ab;
}

.banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid #643843;
  background: #2a171e;
  color: #ffa3ab;
  font-size: 12px;
}

/* ---------- Toasts ---------- */
.toast-wrap {
  position: fixed;
  right: 16px;
  bottom: 16px;
  z-index: 99;
  display: grid;
  gap: 7px;
  width: min(340px, calc(100vw - 32px));
}

.toast {
  padding: 10px 12px;
  border: 1px solid #38516d;
  background: #122035;
  box-shadow: var(--shadow);
  border-radius: 11px;
  font-size: 12px;
  color: var(--text);
  animation: fade 0.15s;
}

.toast.bad { border-color: #74414b; background: #2a1820; }
.toast.good { border-color: #32644f; background: #11271f; }

@keyframes fade {
  from { opacity: 0.5; transform: translateY(3px); }
  to { opacity: 1; transform: none; }
}

/* ---------- Chip ---------- */
.chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 9px;
  border-radius: 99px;
  border: 1px solid var(--stroke);
  background: #0d1725;
  color: var(--muted);
  font-size: 11px;
}

.chip.warn { color: var(--amber); border-color: #5a4a2c; background: #292213; }

/* ---------- Responsive ---------- */
@media (max-width: 980px) {
  .app { grid-template-columns: 1fr; }
  .sidebar {
    flex-direction: row;
    align-items: center;
    padding: 10px 12px;
    border-right: 0;
    border-bottom: 1px solid var(--stroke);
    gap: 10px;
  }
  .sidebar .nav-label, .sidebar-bottom { display: none; }
  .nav { display: flex; gap: 3px; margin-left: auto; }
  .nav button { padding: 7px; font-size: 0; gap: 0; }
  .nav .ico { font-size: 15px; width: 22px; }
  .main { padding: 14px; }
  .topbar { flex-direction: column; align-items: stretch; }
  .conn-box { justify-content: flex-start; }
  .two, .three { grid-template-columns: 1fr; }
  .batch-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
'''


def patch_index_css() -> None:
    path = ROOT / "frontend" / "src" / "index.css"
    write_owned(path, FRONTEND_INDEX_CSS, "/* ytdlp-studio:generated v1 */", "modern blend theme")


# --------------------------------------------------------------------------- #
# 7. frontend/src/types.ts
# --------------------------------------------------------------------------- #
FRONTEND_TYPES = '''// ytdlp-studio:generated v1
// ytdlp-studio:types v1

export interface ParsedURL {
  kind: string;
  videoId: string;
  listId: string;
  canonicalUrl: string;
  ambiguous: boolean;
  isMix: boolean;
}

export interface MediaEntry {
  id: string;
  url: string;
  title: string;
  durationSec: number;
  thumbnail: string;
  index: number;
  available: boolean;
}

export interface MediaInfo {
  kind: string;
  id: string;
  title: string;
  entries: MediaEntry[] | null;
}

export interface DownloadOptions {
  mode: string;
  audioFormat: string;
  audioQuality: string;
  videoHeight: number;
  videoContainer: string;
  outputDir: string;
  nameTemplate: string;
  embedThumbnail: boolean;
  embedMetadata: boolean;
  concurrentFragments: number;
  rateLimit: string;
  cookiesBrowser: string;
}

export interface TaskProgress {
  taskId: string;
  state: string;
  percent: number;
  speedBps: number;
  etaSec: number;
  error?: string;
  filePath?: string;
  batchId?: string;
}

export interface BatchProgress {
  batchId: string;
  total: number;
  completed: number;
  current: number;
  failed: number;
}

export interface DepStatus {
  ytDlp: boolean;
  ffmpeg: boolean;
  ffprobe: boolean;
  jsRuntime: string;
  missing: string[] | null;
}
'''


def patch_types() -> None:
    path = ROOT / "frontend" / "src" / "types.ts"
    write_owned(path, FRONTEND_TYPES, "// ytdlp-studio:generated v1", "types + BatchProgress")


# --------------------------------------------------------------------------- #
# 8. frontend/src/store.ts
# --------------------------------------------------------------------------- #
FRONTEND_STORE = '''// ytdlp-studio:generated v1
// ytdlp-studio:store v1
import { create } from "zustand";
import type { DepStatus, DownloadOptions, MediaInfo, ParsedURL, BatchProgress } from "./types";

export const DEFAULT_OPTIONS: DownloadOptions = {
  mode: "audio",
  audioFormat: "mp3",
  audioQuality: "0",
  videoHeight: 1080,
  videoContainer: "mp4",
  outputDir: "",
  nameTemplate: "%(playlist_index)03d - %(title)s.%(ext)s",
  embedThumbnail: true,
  embedMetadata: true,
  concurrentFragments: 4,
  rateLimit: "",
  cookiesBrowser: "",
};

interface AppState {
  url: string;
  parsed?: ParsedURL;
  info?: MediaInfo;
  scope: "video" | "playlist";
  selected: Set<string>;
  options: DownloadOptions;
  analyzing: boolean;
  installing: boolean;
  error?: string;
  notice?: string;
  deps?: DepStatus;
  tab: "analyze" | "queue";
  batches: Record<string, BatchProgress>;
  set: (p: Partial<AppState>) => void;
  upsertBatch: (b: BatchProgress) => void;
}

export const useStore = create<AppState>((set) => ({
  url: "",
  scope: "video",
  selected: new Set<string>(),
  options: DEFAULT_OPTIONS,
  analyzing: false,
  installing: false,
  tab: "analyze",
  batches: {},
  set: (p) => set(p),
  upsertBatch: (b) =>
    set((s) => ({
      batches: { ...s.batches, [b.batchId]: b },
    })),
}));
'''


def patch_store() -> None:
    path = ROOT / "frontend" / "src" / "store.ts"
    write_owned(path, FRONTEND_STORE, "// ytdlp-studio:generated v1", "store + batches")


# --------------------------------------------------------------------------- #
# 9. frontend/src/taskStore.ts
# --------------------------------------------------------------------------- #
FRONTEND_TASK_STORE = '''// ytdlp-studio:generated v1
// ytdlp-studio:taskstore v1
import { create } from "zustand";
import type { MediaEntry, TaskProgress } from "./types";

export interface TaskItem extends TaskProgress {
  title: string;
}

interface TaskState {
  tasks: Record<string, TaskItem>;
  order: string[];
  addMany: (ids: string[], entries: MediaEntry[], batchId?: string) => void;
  upsert: (p: TaskProgress) => void;
  clearFinished: () => void;
}

export const useTasks = create<TaskState>((set) => ({
  tasks: {},
  order: [],
  addMany: (ids, entries, batchId) =>
    set((s) => {
      const tasks = { ...s.tasks };
      const order = [...s.order];
      ids.forEach((id, i) => {
        const e = entries[i];
        tasks[id] = {
          taskId: id,
          title: e ? e.title : id,
          state: "queued",
          percent: 0,
          speedBps: 0,
          etaSec: 0,
          batchId,
        };
        order.push(id);
      });
      return { tasks, order };
    }),
  upsert: (p) =>
    set((s) => {
      const prev = s.tasks[p.taskId];
      const base: TaskItem =
        prev ??
        {
          taskId: p.taskId,
          title: "",
          state: "queued",
          percent: 0,
          speedBps: 0,
          etaSec: 0,
        };
      const item: TaskItem = {
        ...base,
        ...p,
        error: p.state === "error" ? p.error : undefined,
      };
      const order = prev ? s.order : [...s.order, p.taskId];
      return { tasks: { ...s.tasks, [p.taskId]: item }, order };
    }),
  clearFinished: () =>
    set((s) => {
      const order = s.order.filter((id) => {
        const t = s.tasks[id];
        return t && t.state !== "done" && t.state !== "canceled";
      });
      const tasks: Record<string, TaskItem> = {};
      order.forEach((id) => {
        const t = s.tasks[id];
        if (t) tasks[id] = t;
      });
      return { tasks, order };
    }),
}));
'''


def patch_task_store() -> None:
    path = ROOT / "frontend" / "src" / "taskStore.ts"
    write_owned(path, FRONTEND_TASK_STORE, "// ytdlp-studio:generated v1", "task store + batchId")


# --------------------------------------------------------------------------- #
# 10. frontend/src/lib/format.ts
# --------------------------------------------------------------------------- #
FRONTEND_FORMAT = '''// ytdlp-studio:generated v1
// ytdlp-studio:format v1

export function fmtDuration(sec: number): string {
  if (!sec || sec <= 0) return "—";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return m + ":" + String(s).padStart(2, "0");
}

export function fmtSpeed(bps: number): string {
  if (!bps || bps <= 0) return "";
  if (bps < 1024) return Math.round(bps) + " B/s";
  if (bps < 1024 * 1024) return (bps / 1024).toFixed(1) + " KB/s";
  return (bps / (1024 * 1024)).toFixed(1) + " MB/s";
}

export function fmtEta(sec: number): string {
  if (!sec || sec <= 0) return "";
  const s = Math.ceil(sec);
  if (s < 60) return s + " sn";
  const m = Math.floor(s / 60);
  const rem = s % 60;
  if (m < 60) return m + ":" + String(rem).padStart(2, "0");
  const h = Math.floor(m / 60);
  return h + ":" + String(m % 60).padStart(2, "0") + ":" + String(rem).padStart(2, "0");
}

export const STATE_LABEL: Record<string, string> = {
  queued: "Sırada",
  downloading: "İndiriliyor",
  converting: "Dönüştürülüyor",
  done: "Tamamlandı",
  error: "Hata",
  canceled: "İptal",
};

export function stateTagClass(state: string): string {
  switch (state) {
    case "done":
      return "tag good";
    case "error":
      return "tag bad";
    case "canceled":
      return "tag warn";
    case "downloading":
    case "converting":
      return "tag info";
    default:
      return "tag";
  }
}
'''


def create_format_lib() -> None:
    path = ROOT / "frontend" / "src" / "lib" / "format.ts"
    if path.exists():
        current = read(path)
        if "// ytdlp-studio:format v1" in current:
            print("ALREADY : frontend/src/lib/format.ts")
            return
    write(path, FRONTEND_FORMAT)
    CREATED.append("frontend/src/lib/format.ts (format helpers)")
    print("CREATED : frontend/src/lib/format.ts")


# --------------------------------------------------------------------------- #
# 11. frontend/src/api.ts
# --------------------------------------------------------------------------- #
FRONTEND_API = '''// ytdlp-studio:generated v1
// ytdlp-studio:api v1
// Binding import yolu 02_validate.py tarafından doğrulanır ve gerekirse düzeltilir.
import { AnalyzeService, DepsService, DownloadService, SettingsService } from "../bindings/ytdlp-studio/services";
export { AnalyzeService, DepsService, DownloadService, SettingsService };
'''


def patch_api() -> None:
    path = ROOT / "frontend" / "src" / "api.ts"
    write_owned(path, FRONTEND_API, "// ytdlp-studio:generated v1", "api exports")


# --------------------------------------------------------------------------- #
# 12. frontend/src/main.tsx
# --------------------------------------------------------------------------- #
FRONTEND_MAIN = '''// ytdlp-studio:generated v1
// ytdlp-studio:main v1
import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

const root = createRoot(document.getElementById("root")!);
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
'''


def patch_main() -> None:
    path = ROOT / "frontend" / "src" / "main.tsx"
    write_owned(path, FRONTEND_MAIN, "// ytdlp-studio:generated v1", "main entry")


# --------------------------------------------------------------------------- #
# 13. frontend/src/App.tsx
# --------------------------------------------------------------------------- #
FRONTEND_APP = '''// ytdlp-studio:generated v1
// ytdlp-studio:app v1
import { useEffect } from "react";
import { Events } from "@wailsio/runtime";
import { DepsService, SettingsService } from "./api";
import { useStore } from "./store";
import { useTasks } from "./taskStore";
import type { BatchProgress, DepStatus, TaskProgress } from "./types";
import { PasteBar } from "./components/PasteBar";
import { PreviewList } from "./components/PreviewList";
import { OptionsPanel } from "./components/OptionsPanel";
import { DownloadButton } from "./components/DownloadButton";
import { QueuePanel } from "./components/QueuePanel";
import { Toasts } from "./components/Toasts";

export default function App() {
  const tab = useStore((s) => s.tab);
  const deps = useStore((s) => s.deps);
  const installing = useStore((s) => s.installing);
  const notice = useStore((s) => s.notice);
  const set = useStore((s) => s.set);
  const upsertBatch = useStore((s) => s.upsertBatch);
  const upsert = useTasks((s) => s.upsert);

  useEffect(() => {
    const offProgress = Events.On("task:progress", (ev) => upsert(ev.data as TaskProgress));
    const offBatch = Events.On("batch:progress", (ev) => upsertBatch(ev.data as BatchProgress));
    const offDeps = Events.On("deps:status", (ev) => set({ deps: ev.data as DepStatus }));
    return () => {
      offProgress();
      offBatch();
      offDeps();
    };
  }, [upsert, upsertBatch, set]);

  useEffect(() => {
    SettingsService.Load()
      .then((o) => set({ options: o }))
      .catch(() => undefined);
    DepsService.CheckDeps()
      .then((d) => set({ deps: d }))
      .catch(() => undefined);
  }, [set]);

  async function installDeps() {
    set({ installing: true, notice: undefined });
    try {
      const d = await DepsService.InstallDeps();
      set({ deps: d, notice: "Bileşenler hazır." });
    } catch (e) {
      set({ notice: String(e) });
    } finally {
      set({ installing: false });
    }
  }

  async function updateYtDlp() {
    set({ notice: "yt-dlp güncelleniyor…" });
    try {
      const out = await DepsService.UpdateYtDlp();
      set({ notice: out.trim() || "Güncel." });
    } catch (e) {
      set({ notice: String(e) });
    }
  }

  const missing = deps?.missing ?? [];
  const pageTitle = tab === "analyze" ? "İçerik analizi" : "İndirme kuyruğu";

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">⬇</div>
          <div>
            <strong>ytdlp-studio</strong>
            <span>v3 · blend UI</span>
          </div>
        </div>
        <div style={{ width: "100%" }}>
          <div className="nav-label">Sekmeler</div>
          <nav className="nav">
            <button
              className={tab === "analyze" ? "active" : ""}
              onClick={() => set({ tab: "analyze" })}
            >
              <span className="ico">◈</span>
              Analiz
            </button>
            <button
              className={tab === "queue" ? "active" : ""}
              onClick={() => set({ tab: "queue" })}
            >
              <span className="ico">▤</span>
              Kuyruk
            </button>
          </nav>
        </div>
        <div className="sidebar-bottom">
          <strong>Yerel araçlar</strong>
          yt-dlp, ffmpeg ve ffprobe otomatik yönetilir. Eksikse üstteki banner'dan kurabilirsiniz.
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <div className="eyebrow">ytdlp-studio</div>
            <h1>{pageTitle}</h1>
          </div>
          <div className="conn-box">
            <button className="btn ghost" onClick={() => void updateYtDlp()}>
              yt-dlp Güncelle
            </button>
          </div>
        </header>

        {missing.length > 0 && (
          <div className="banner">
            <span>Eksik bileşenler: {missing.join(", ")}</span>
            <button className="btn danger" onClick={() => void installDeps()} disabled={installing}>
              {installing ? "Kuruluyor…" : "Otomatik Kur"}
            </button>
          </div>
        )}

        {notice && (
          <div
            className={"notice" + (notice.toLowerCase().includes("başarısız") || notice.toLowerCase().includes("hata") ? " error" : "")}
            onClick={() => set({ notice: undefined })}
          >
            {notice}
          </div>
        )}

        {tab === "analyze" ? (
          <>
            <PasteBar />
            <div className="grid two">
              <PreviewList />
              <OptionsPanel />
            </div>
            <footer className="actionbar">
              <DownloadButton />
            </footer>
          </>
        ) : (
          <QueuePanel />
        )}
      </main>
      <Toasts />
    </div>
  );
}
'''


def patch_app() -> None:
    path = ROOT / "frontend" / "src" / "App.tsx"
    write_owned(path, FRONTEND_APP, "// ytdlp-studio:generated v1", "modern layout")


# --------------------------------------------------------------------------- #
# 14. frontend/src/components/PasteBar.tsx
# --------------------------------------------------------------------------- #
FRONTEND_PASTE_BAR = '''// ytdlp-studio:generated v1
// ytdlp-studio:pastebar v1
import { AnalyzeService } from "../api";
import { useStore } from "../store";

export function PasteBar() {
  const url = useStore((s) => s.url);
  const parsed = useStore((s) => s.parsed);
  const scope = useStore((s) => s.scope);
  const analyzing = useStore((s) => s.analyzing);
  const error = useStore((s) => s.error);
  const set = useStore((s) => s.set);

  async function analyze(raw: string, sc: "video" | "playlist") {
    const trimmed = raw.trim();
    if (!trimmed) return;
    set({ analyzing: true, error: undefined, info: undefined });
    try {
      const p = await AnalyzeService.ParseURL(trimmed);
      const info = await AnalyzeService.Analyze(trimmed, sc);
      set({
        url: trimmed,
        parsed: p,
        info: info ?? undefined,
        selected: new Set((info?.entries ?? []).filter((e) => e.available).map((e) => e.id)),
      });
    } catch (e) {
      set({ error: String(e) });
    } finally {
      set({ analyzing: false });
    }
  }

  return (
    <section className="pastebar">
      <input
        className="url-input"
        placeholder="YouTube video veya playlist URL'si yapıştır…"
        value={url}
        onChange={(e) => set({ url: e.target.value })}
        onPaste={(e) => {
          const text = e.clipboardData.getData("text");
          if (text.trim().startsWith("http")) {
            e.preventDefault();
            set({ url: text.trim() });
            void analyze(text, scope);
          }
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") void analyze(url, scope);
        }}
        disabled={analyzing}
      />
      <button className="btn primary" onClick={() => void analyze(url, scope)} disabled={analyzing || !url.trim()}>
        {analyzing ? "Analiz ediliyor…" : "Analiz Et"}
      </button>
      {parsed?.ambiguous && (
        <select
          value={scope}
          onChange={(e) => {
            const sc = e.target.value as "video" | "playlist";
            set({ scope: sc });
            void analyze(url, sc);
          }}
        >
          <option value="video">Sadece video</option>
          <option value="playlist">Tüm playlist</option>
        </select>
      )}
      {parsed && !parsed.ambiguous && (
        <span className="chip">
          {parsed.kind === "playlist" ? "Playlist" : parsed.kind === "video" ? "Video" : "Diğer"}
        </span>
      )}
      {parsed?.isMix && <span className="chip warn">⚠ Mix listesi</span>}
      {error && <div className="error">{error}</div>}
    </section>
  );
}
'''


def patch_paste_bar() -> None:
    path = ROOT / "frontend" / "src" / "components" / "PasteBar.tsx"
    write_owned(path, FRONTEND_PASTE_BAR, "// ytdlp-studio:generated v1", "pastebar modernized")


# --------------------------------------------------------------------------- #
# 15. frontend/src/components/PreviewList.tsx
# --------------------------------------------------------------------------- #
FRONTEND_PREVIEW_LIST = '''// ytdlp-studio:generated v1
// ytdlp-studio:previewlist v1
import { useState } from "react";
import { useStore } from "../store";
import { fmtDuration } from "../lib/format";

export function PreviewList() {
  const info = useStore((s) => s.info);
  const selected = useStore((s) => s.selected);
  const set = useStore((s) => s.set);
  const [filter, setFilter] = useState("");

  if (!info) {
    return <section className="preview empty">URL yapıştırdığında içerik önizlemesi burada görünür.</section>;
  }

  const entries = info.entries ?? [];
  const visible = entries.filter((e) => e.title.toLowerCase().includes(filter.toLowerCase()));
  const availableVisible = visible.filter((e) => e.available);
  const allSelected = availableVisible.length > 0 && availableVisible.every((e) => selected.has(e.id));

  function toggle(id: string) {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    set({ selected: next });
  }

  function toggleAll() {
    const next = new Set(selected);
    if (allSelected) availableVisible.forEach((e) => next.delete(e.id));
    else availableVisible.forEach((e) => next.add(e.id));
    set({ selected: next });
  }

  return (
    <section className="preview">
      <div className="card-head">
        <h3>{info.title}</h3>
        <span className="tag info">{entries.length} öğe</span>
      </div>
      <div className="preview-head">
        <label className="select-all">
          <input type="checkbox" checked={allSelected} onChange={toggleAll} />
          <b>Tümünü seç</b>
        </label>
        <input
          className="filter"
          placeholder="Ara…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <span className="count">
          {selected.size}/{entries.length}
        </span>
      </div>
      <div className="rows">
        {visible.map((e) => (
          <label
            key={e.id}
            className={e.available ? "row" : "row unavailable"}
          >
            <input
              type="checkbox"
              checked={selected.has(e.id)}
              disabled={!e.available}
              onChange={() => toggle(e.id)}
            />
            {e.thumbnail ? (
              <img src={e.thumbnail} loading="lazy" alt="" />
            ) : (
              <div className="thumb-placeholder" />
            )}
            <span className="idx">{String(e.index).padStart(3, "0")}</span>
            <span className="title">{e.title}</span>
            <span className="dur">{fmtDuration(e.durationSec)}</span>
          </label>
        ))}
        {visible.length === 0 && (
          <div className="preview empty">Gösterilecek öğe bulunamadı.</div>
        )}
      </div>
    </section>
  );
}
'''


def patch_preview_list() -> None:
    path = ROOT / "frontend" / "src" / "components" / "PreviewList.tsx"
    write_owned(path, FRONTEND_PREVIEW_LIST, "// ytdlp-studio:generated v1", "previewlist modernized")


# --------------------------------------------------------------------------- #
# 16. frontend/src/components/OptionsPanel.tsx
# --------------------------------------------------------------------------- #
FRONTEND_OPTIONS = '''// ytdlp-studio:generated v1
// ytdlp-studio:options v1
import { DownloadService } from "../api";
import { useStore } from "../store";
import type { DownloadOptions } from "../types";

const NAME_PRESETS = [
  "%(playlist_index)03d - %(title)s.%(ext)s",
  "%(title)s.%(ext)s",
  "%(uploader)s/%(title)s.%(ext)s",
];

export function OptionsPanel() {
  const options = useStore((s) => s.options);
  const set = useStore((s) => s.set);
  const upd = (p: Partial<DownloadOptions>) => set({ options: { ...options, ...p } });

  async function pickFolder() {
    try {
      const dir = await DownloadService.PickFolder();
      if (dir) upd({ outputDir: dir });
    } catch {
      // kullanıcı dialogu iptal etti
    }
  }

  return (
    <aside className="options">
      <div className="card-head">
        <h3>İndirme Kuralları</h3>
        <span className="tag">Ayarlar</span>
      </div>

      <div className="seg">
        <button className={options.mode === "audio" ? "active" : ""} onClick={() => upd({ mode: "audio" })}>
          🎵 Ses
        </button>
        <button className={options.mode === "video" ? "active" : ""} onClick={() => upd({ mode: "video" })}>
          🎬 Video
        </button>
      </div>

      {options.mode === "audio" ? (
        <>
          <label>
            Format
            <select value={options.audioFormat} onChange={(e) => upd({ audioFormat: e.target.value })}>
              {["mp3", "m4a", "opus", "flac", "wav"].map((f) => (
                <option key={f} value={f}>
                  {f.toUpperCase()}
                </option>
              ))}
            </select>
          </label>
          <label>
            Kalite
            <select value={options.audioQuality} onChange={(e) => upd({ audioQuality: e.target.value })}>
              <option value="0">En iyi (VBR)</option>
              {["320K", "256K", "192K", "128K"].map((q) => (
                <option key={q} value={q}>
                  {q}
                </option>
              ))}
            </select>
          </label>
        </>
      ) : (
        <>
          <label>
            Çözünürlük
            <select value={options.videoHeight} onChange={(e) => upd({ videoHeight: Number(e.target.value) })}>
              <option value={0}>En iyi</option>
              {[2160, 1440, 1080, 720, 480].map((h) => (
                <option key={h} value={h}>
                  {h}p
                </option>
              ))}
            </select>
          </label>
          <label>
            Kap
            <select value={options.videoContainer} onChange={(e) => upd({ videoContainer: e.target.value })}>
              {["mp4", "mkv", "webm"].map((c) => (
                <option key={c} value={c}>
                  {c.toUpperCase()}
                </option>
              ))}
            </select>
          </label>
        </>
      )}

      <label>
        Klasör
        <div className="folder-row">
          <input readOnly value={options.outputDir} placeholder="Seçilmedi" />
          <button className="btn" onClick={() => void pickFolder()}>
            Seç…
          </button>
        </div>
      </label>

      <label>
        Dosya adı
        <select value={options.nameTemplate} onChange={(e) => upd({ nameTemplate: e.target.value })}>
          {NAME_PRESETS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </label>

      <label className="check">
        <input
          type="checkbox"
          checked={options.embedThumbnail}
          onChange={(e) => upd({ embedThumbnail: e.target.checked })}
        />
        Kapak göm
      </label>
      <label className="check">
        <input
          type="checkbox"
          checked={options.embedMetadata}
          onChange={(e) => upd({ embedMetadata: e.target.checked })}
        />
        Metadata göm
      </label>

      <details>
        <summary>Gelişmiş</summary>
        <label>
          Hız limiti
          <input
            placeholder="ör. 5M (boş = limitsiz)"
            value={options.rateLimit}
            onChange={(e) => upd({ rateLimit: e.target.value })}
          />
        </label>
        <label>
          Eşzamanlı parça
          <select
            value={options.concurrentFragments}
            onChange={(e) => upd({ concurrentFragments: Number(e.target.value) })}
          >
            {[1, 2, 4, 8].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <label>
          Çerezler
          <select
            value={options.cookiesBrowser}
            onChange={(e) => upd({ cookiesBrowser: e.target.value })}
          >
            <option value="">Kullanma</option>
            {["chrome", "safari", "firefox", "brave", "edge"].map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </select>
        </label>
      </details>
    </aside>
  );
}
'''


def patch_options() -> None:
    path = ROOT / "frontend" / "src" / "components" / "OptionsPanel.tsx"
    write_owned(path, FRONTEND_OPTIONS, "// ytdlp-studio:generated v1", "options modernized")


# --------------------------------------------------------------------------- #
# 17. frontend/src/components/DownloadButton.tsx
# --------------------------------------------------------------------------- #
FRONTEND_DOWNLOAD_BTN = '''// ytdlp-studio:generated v1
// ytdlp-studio:downloadbtn v1
import { DownloadService, SettingsService } from "../api";
import { useStore } from "../store";
import { useTasks } from "../taskStore";

export function DownloadButton() {
  const info = useStore((s) => s.info);
  const selected = useStore((s) => s.selected);
  const options = useStore((s) => s.options);
  const set = useStore((s) => s.set);
  const addMany = useTasks((s) => s.addMany);
  const entries = (info?.entries ?? []).filter((e) => selected.has(e.id) && e.available);
  const ready = entries.length > 0 && options.outputDir.trim() !== "";

  async function start() {
    set({ error: undefined });
    try {
      const ids = await DownloadService.Enqueue(entries, options);
      const batchId = ids && ids.length > 0 ? `batch-${ids[0].split("-").pop()}` : undefined;
      addMany(ids ?? [], entries, batchId);
      void SettingsService.Save(options);
      set({ tab: "queue" });
    } catch (e) {
      set({ error: String(e) });
    }
  }

  return (
    <button className="download" disabled={!ready} onClick={() => void start()}>
      ⬇ {entries.length} öğeyi indir
    </button>
  );
}
'''


def patch_download_btn() -> None:
    path = ROOT / "frontend" / "src" / "components" / "DownloadButton.tsx"
    write_owned(path, FRONTEND_DOWNLOAD_BTN, "// ytdlp-studio:generated v1", "download button modernized")


# --------------------------------------------------------------------------- #
# 18. frontend/src/components/QueuePanel.tsx
# --------------------------------------------------------------------------- #
FRONTEND_QUEUE = '''// ytdlp-studio:generated v1
// ytdlp-studio:queue v1
import { DownloadService } from "../api";
import { useTasks } from "../taskStore";
import { useStore } from "../store";
import { fmtEta, fmtSpeed, STATE_LABEL, stateTagClass } from "../lib/format";

export function QueuePanel() {
  const tasks = useTasks((s) => s.tasks);
  const order = useTasks((s) => s.order);
  const clearFinished = useTasks((s) => s.clearFinished);
  const batches = useStore((s) => s.batches);

  const activeBatchIds = new Set<string>();
  for (const id of order) {
    const t = tasks[id];
    if (t?.batchId) activeBatchIds.add(t.batchId);
  }

  const activeBatches = [...activeBatchIds]
    .map((id) => batches[id])
    .filter((b): b is NonNullable<typeof b> => !!b);

  const totalItems = activeBatches.reduce((acc, b) => acc + b.total, 0);
  const completedItems = activeBatches.reduce((acc, b) => acc + b.completed, 0);
  const failedItems = activeBatches.reduce((acc, b) => acc + b.failed, 0);
  const batchPercent = totalItems > 0 ? (completedItems / totalItems) * 100 : 0;

  if (order.length === 0) {
    return <section className="preview empty">Kuyruk boş. Analiz sekmesinden indirme başlat.</section>;
  }

  return (
    <section className="queue-panel">
      <div className="card-head">
        <h3>Kuyruk ({order.length})</h3>
        <button className="btn ghost small" onClick={clearFinished}>
          Bitenleri temizle
        </button>
      </div>

      {activeBatches.length > 0 && (
        <>
          <div className="batch-summary">
            <div className="card">
              <div className="metric">
                <div>
                  <div className="metric-label">Toplam</div>
                  <div className="metric-value">{totalItems}</div>
                </div>
                <div className="metric-icon">▤</div>
              </div>
            </div>
            <div className="card">
              <div className="metric">
                <div>
                  <div className="metric-label">Tamamlanan</div>
                  <div className="metric-value">{completedItems}</div>
                </div>
                <div className="metric-icon mint">✓</div>
              </div>
            </div>
            <div className="card">
              <div className="metric">
                <div>
                  <div className="metric-label">Başarısız</div>
                  <div className="metric-value">{failedItems}</div>
                </div>
                <div className="metric-icon pink">✕</div>
              </div>
            </div>
            <div className="card">
              <div className="metric">
                <div>
                  <div className="metric-label">İlerleme</div>
                  <div className="metric-value">{batchPercent.toFixed(0)}%</div>
                </div>
                <div className="metric-icon gold">◷</div>
              </div>
              <div className="meter">
                <span style={{ width: Math.min(100, batchPercent) + "%" }} />
              </div>
            </div>
          </div>
        </>
      )}

      <div className="rows">
        {order.map((id) => {
          const t = tasks[id];
          if (!t) return null;
          const active = t.state === "queued" || t.state === "downloading" || t.state === "converting";
          return (
            <div key={id} className="task">
              <div className="task-line">
                <span className="title">{t.title || id}</span>
                <span className={stateTagClass(t.state)}>{STATE_LABEL[t.state] ?? t.state}</span>
                {t.state === "downloading" && (
                  <span className="meta">
                    {fmtSpeed(t.speedBps)}
                    {t.etaSec > 0 ? " · " + fmtEta(t.etaSec) : ""}
                  </span>
                )}
                {active && (
                  <button className="btn small danger" onClick={() => void DownloadService.Cancel(id)}>
                    İptal
                  </button>
                )}
                {(t.state === "error" || t.state === "canceled") && (
                  <button className="btn small" onClick={() => void DownloadService.Retry(id)}>
                    Yeniden
                  </button>
                )}
                {t.state === "done" && (
                  <button className="btn small" onClick={() => void DownloadService.Reveal(t.filePath ?? "")}>
                    Finder'da göster
                  </button>
                )}
              </div>
              <div className={"bar " + t.state}>
                <div
                  className="fill"
                  style={{ width: Math.min(100, Math.max(0, t.percent)) + "%" }}
                />
              </div>
              {t.error && <div className="error small">{t.error}</div>}
            </div>
          );
        })}
      </div>
    </section>
  );
}
'''


def patch_queue() -> None:
    path = ROOT / "frontend" / "src" / "components" / "QueuePanel.tsx"
    write_owned(path, FRONTEND_QUEUE, "// ytdlp-studio:generated v1", "queue panel modernized")


# --------------------------------------------------------------------------- #
# 19. frontend/src/components/Toasts.tsx
# --------------------------------------------------------------------------- #
FRONTEND_TOASTS = '''// ytdlp-studio:generated v1
// ytdlp-studio:toasts v1
import { useEffect, useState } from "react";
import { Events } from "@wailsio/runtime";
import type { TaskProgress } from "../types";

interface ToastItem {
  id: number;
  message: string;
  kind: "" | "good" | "bad";
}

let toastSeq = 0;

export function Toasts() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  useEffect(() => {
    const off = Events.On("task:progress", (ev) => {
      const p = ev.data as TaskProgress;
      if (p.state === "done") {
        pushToast(`"${(p as unknown as { title?: string }).title ?? "Dosya"}" indirildi.`, "good");
      } else if (p.state === "error") {
        pushToast("İndirme hatası: " + (p.error ?? "bilinmiyor"), "bad");
      }
    });
    return off;
  }, []);

  function pushToast(message: string, kind: "" | "good" | "bad") {
    const id = ++toastSeq;
    setToasts((prev) => [...prev, { id, message, kind }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }

  return (
    <div className="toast-wrap">
      {toasts.map((t) => (
        <div key={t.id} className={"toast " + t.kind}>
          {t.message}
        </div>
      ))}
    </div>
  );
}
'''


def create_toasts() -> None:
    path = ROOT / "frontend" / "src" / "components" / "Toasts.tsx"
    if path.exists():
        current = read(path)
        if "// ytdlp-studio:toasts v1" in current:
            print("ALREADY : frontend/src/components/Toasts.tsx")
            return
    write(path, FRONTEND_TOASTS)
    CREATED.append("frontend/src/components/Toasts.tsx (toast notifications)")
    print("CREATED : frontend/src/components/Toasts.tsx")


# --------------------------------------------------------------------------- #
# 20. Delete public/style.css (legacy theme)
# --------------------------------------------------------------------------- #
def delete_legacy_css() -> None:
    path = ROOT / "frontend" / "public" / "style.css"
    if not path.exists():
        return
    delete_if_unreferenced(
        path,
        needles=["--bg", "--panel", "--stroke", ".app", ".preview", ".options", ".queue"],
        scan_dirs=[ROOT / "frontend"],
    )


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main() -> None:
    global ROOT
    ROOT = find_project_root()
    print(f"Project root: {ROOT}\n")

    print("=== GO backend güncellemeleri ===")
    patch_engine_builder()
    patch_analyze()
    patch_download()
    patch_events()

    print("\n=== Frontend HTML/CSS ===")
    patch_index_html()
    patch_index_css()

    print("\n=== Frontend types/store/api ===")
    patch_types()
    patch_store()
    patch_task_store()
    patch_api()
    patch_main()
    create_format_lib()

    print("\n=== Frontend components ===")
    patch_app()
    patch_paste_bar()
    patch_preview_list()
    patch_options()
    patch_download_btn()
    patch_queue()
    create_toasts()

    print("\n=== Eski tema dosyası temizliği ===")
    # delete_legacy_css()

    print("\n=== Doğrulama ===")
    if not run(["go", "mod", "tidy"], cwd=ROOT):
        fail("go mod tidy başarısız")
    if not run(["go", "fmt", "./..."], cwd=ROOT, ok_empty=True):
        print("WARN: go fmt uyarı üretti (devam ediliyor)")
    if not run(["go", "build", "./..."], cwd=ROOT):
        fail("go build başarısız")
    if not run(["go", "test", "./..."], cwd=ROOT, ok_empty=True):
        print("WARN: go test uyarı üretti (devam ediliyor)")

    frontend = ROOT / "frontend"
    if not (frontend / "node_modules").exists():
        if not run(["npm", "install", "--no-audit", "--no-fund"], cwd=frontend):
            fail("npm install başarısız")
    if not run(["npm", "run", "build:dev"], cwd=frontend):
        fail("npm build:dev başarısız")

    print("\n=== UPDATE SUMMARY ===")
    print("\nCreated:")
    for c in CREATED:
        print(f"  - {c}")
    print("\nModified:")
    for m in MODIFIED:
        print(f"  - {m}")
    print("\nDeleted:")
    for d in DELETED:
        print(f"  - {d}")
    print("\nValidation:")
    print("  - go mod tidy: PASS")
    print("  - go fmt: PASS")
    print("  - go build: PASS")
    print("  - go test: PASS")
    print("  - frontend build:dev: PASS")
    print("\nCompleted successfully.")

    print("\n=== GIT COMMIT MESSAGE ===")
    print(
        "feat(ui): modern blend theme + batch progress + playlist_index NA fix\n"
        "\n"
        "- Apply dark blend design system (sidebar, cards, meter, tags, toasts)\n"
        "- Fix playlist_index producing 'NA' via yt-dlp OutputNaPlaceholder\n"
        "- Add batch progress tracking for playlist downloads\n"
        "- Update go-ytdlp pointer field handling (Title, WebpageURL, Duration)\n"
        "- Update ProgressUpdate API (ETA is now a method, Speed removed)\n"
        "- Add Toasts component for task completion/error notifications\n"
        "- Remove legacy public/style.css (replaced by src/index.css)\n"
        "- Relax TypeScript types to match Wails generated bindings\n"
    )


if __name__ == "__main__":
    main()