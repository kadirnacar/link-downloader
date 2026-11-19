#!/usr/bin/env python3
# 01_apply_changes.py — analizdeki tüm değişiklikleri gerçek dosya işlemleriyle uygular.
import json
import re
import shutil

from _common import (MARKER, Report, base_parser, delete_file, die, find_root,
                     go_env, guard_main, patch_title, read, replace_file, run,
                     write_generated, write_verified)

GO_FILES = {}
TS_FILES = {}

GO_FILES["internal/model/media.go"] = r"""// ytdlp-studio:generated v1
package model

type ParsedURL struct {
	Kind         string `json:"kind"`
	VideoID      string `json:"videoId"`
	ListID       string `json:"listId"`
	CanonicalURL string `json:"canonicalUrl"`
	Ambiguous    bool   `json:"ambiguous"`
	IsMix        bool   `json:"isMix"`
}

type MediaEntry struct {
	ID          string  `json:"id"`
	URL         string  `json:"url"`
	Title       string  `json:"title"`
	DurationSec float64 `json:"durationSec"`
	Thumbnail   string  `json:"thumbnail"`
	Index       int     `json:"index"`
	Available   bool    `json:"available"`
}

type MediaInfo struct {
	Kind    string       `json:"kind"`
	ID      string       `json:"id"`
	Title   string       `json:"title"`
	Entries []MediaEntry `json:"entries"`
}
"""

GO_FILES["internal/model/options.go"] = r"""// ytdlp-studio:generated v1
package model

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

type DownloadOptions struct {
	Mode                string `json:"mode"`
	AudioFormat         string `json:"audioFormat"`
	AudioQuality        string `json:"audioQuality"`
	VideoHeight         int    `json:"videoHeight"`
	VideoContainer      string `json:"videoContainer"`
	OutputDir           string `json:"outputDir"`
	NameTemplate        string `json:"nameTemplate"`
	EmbedThumbnail      bool   `json:"embedThumbnail"`
	EmbedMetadata       bool   `json:"embedMetadata"`
	ConcurrentFragments int    `json:"concurrentFragments"`
	RateLimit           string `json:"rateLimit"`
	CookiesBrowser      string `json:"cookiesBrowser"`
}

func DefaultOptions() DownloadOptions {
	home, _ := os.UserHomeDir()
	out := ""
	if home != "" {
		out = filepath.Join(home, "Downloads")
	}
	return DownloadOptions{
		Mode:                "audio",
		AudioFormat:         "mp3",
		AudioQuality:        "0",
		VideoHeight:         1080,
		VideoContainer:      "mp4",
		OutputDir:           out,
		NameTemplate:        "%(playlist_index)03d - %(title)s.%(ext)s",
		EmbedThumbnail:      true,
		EmbedMetadata:       true,
		ConcurrentFragments: 4,
	}
}

var qualityRe = regexp.MustCompile("^(?:[0-9]|10|[0-9]+K)$")

func Validate(o DownloadOptions) error {
	if o.Mode != "audio" && o.Mode != "video" {
		return fmt.Errorf("geçersiz indirme tipi: %q", o.Mode)
	}
	if o.Mode == "audio" {
		switch o.AudioFormat {
		case "mp3", "m4a", "opus", "flac", "wav":
		default:
			return fmt.Errorf("geçersiz ses formatı: %q", o.AudioFormat)
		}
		if !qualityRe.MatchString(o.AudioQuality) {
			return fmt.Errorf("geçersiz ses kalitesi: %q", o.AudioQuality)
		}
	} else {
		switch o.VideoContainer {
		case "mp4", "mkv", "webm":
		default:
			return fmt.Errorf("geçersiz video kabı: %q", o.VideoContainer)
		}
		switch o.VideoHeight {
		case 0, 360, 480, 720, 1080, 1440, 2160:
		default:
			return fmt.Errorf("geçersiz çözünürlük: %d", o.VideoHeight)
		}
	}
	if strings.TrimSpace(o.OutputDir) == "" {
		return errors.New("indirme klasörü seçilmedi")
	}
	if !strings.Contains(o.NameTemplate, ".%(ext)s") {
		return errors.New("dosya adı şablonu .%(ext)s içermeli")
	}
	if o.ConcurrentFragments < 1 || o.ConcurrentFragments > 16 {
		return errors.New("concurrentFragments 1-16 arası olmalı")
	}
	return nil
}
"""

GO_FILES["internal/model/options_test.go"] = r"""// ytdlp-studio:generated v1
package model

import "testing"

func TestDefaultOptionsValid(t *testing.T) {
	o := DefaultOptions()
	if o.OutputDir == "" {
		t.Skip("home dizini bulunamadı")
	}
	if err := Validate(o); err != nil {
		t.Fatalf("varsayılanlar geçersiz: %v", err)
	}
}

func TestValidateRejects(t *testing.T) {
	base := DefaultOptions()
	muts := []func(o *DownloadOptions){
		func(o *DownloadOptions) { o.Mode = "gif" },
		func(o *DownloadOptions) { o.AudioFormat = "ogg" },
		func(o *DownloadOptions) { o.AudioQuality = "99" },
		func(o *DownloadOptions) { o.OutputDir = "" },
		func(o *DownloadOptions) { o.NameTemplate = "%(title)s" },
		func(o *DownloadOptions) { o.ConcurrentFragments = 0 },
	}
	for i, mut := range muts {
		o := base
		mut(&o)
		if err := Validate(o); err == nil {
			t.Fatalf("case %d: hata bekleniyordu", i)
		}
	}
}
"""

GO_FILES["internal/engine/builder.go"] = r"""// ytdlp-studio:generated v1
package engine

import (
	"fmt"
	"sync"

	"github.com/lrstanley/go-ytdlp"

	"__MODULE__/internal/model"
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
		Output(o.NameTemplate)
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
"""

GO_FILES["services/analyze.go"] = r"""// ytdlp-studio:generated v1
package services

import (
	"context"
	"errors"
	"fmt"
	"net/url"
	"strings"
	"time"

	"github.com/lrstanley/go-ytdlp"

	"__MODULE__/internal/engine"
	"__MODULE__/internal/model"
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

	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Minute)
	defer cancel()
	infos, _, err := engine.NewCommand().FlatPlaylist().ExtractInfo(ctx, target)
	if err != nil {
		return nil, fmt.Errorf("içerik analizi başarısız: %w", err)
	}
	if len(infos) == 0 || infos[0] == nil {
		return nil, errors.New("içerik bulunamadı")
	}
	info := infos[0]
	out := &model.MediaInfo{Kind: "video", ID: info.ID, Title: info.Title}
	entries := []*ytdlp.ExtractedInfo{info}
	if len(info.Entries) > 0 {
		out.Kind, entries = "playlist", info.Entries
	}
	for i, e := range entries {
		if e == nil {
			continue
		}
		me := model.MediaEntry{
			ID:          e.ID,
			URL:         e.WebpageURL,
			Title:       e.Title,
			DurationSec: e.Duration,
			Index:       i + 1,
			Available:   e.Title != "[Private video]" && e.Title != "[Deleted video]",
		}
		if me.URL == "" {
			me.URL = "https://www.youtube.com/watch?v=" + e.ID
		}
		me.Thumbnail = thumbOf(e)
		out.Entries = append(out.Entries, me)
	}
	return out, nil
}

func thumbOf(e *ytdlp.ExtractedInfo) string {
	if len(e.Thumbnails) > 0 {
		return e.Thumbnails[len(e.Thumbnails)-1].URL
	}
	if len(e.ID) == 11 {
		return "https://i.ytimg.com/vi/" + e.ID + "/hqdefault.jpg"
	}
	return ""
}
"""

GO_FILES["services/analyze_test.go"] = r"""// ytdlp-studio:generated v1
package services

import "testing"

func TestParseURL(t *testing.T) {
	s := &AnalyzeService{}
	cases := []struct {
		name, raw, kind, video, list string
		ambiguous, mix, wantErr      bool
	}{
		{"video", "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "video", "dQw4w9WgXcQ", "", false, false, false},
		{"short", "https://youtu.be/dQw4w9WgXcQ?si=abc", "video", "dQw4w9WgXcQ", "", false, false, false},
		{"playlist", "https://www.youtube.com/playlist?list=PLabc123", "playlist", "", "PLabc123", false, false, false},
		{"ambiguous", "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLabc123", "video", "dQw4w9WgXcQ", "PLabc123", true, false, false},
		{"shorts", "https://www.youtube.com/shorts/dQw4w9WgXcQ", "video", "dQw4w9WgXcQ", "", false, false, false},
		{"mix", "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=RDdQw4w9WgXcQ", "video", "dQw4w9WgXcQ", "RDdQw4w9WgXcQ", true, true, false},
		{"music", "https://music.youtube.com/watch?v=dQw4w9WgXcQ", "video", "dQw4w9WgXcQ", "", false, false, false},
		{"other", "https://vimeo.com/123456", "unknown", "", "", false, false, false},
		{"invalid", "bu bir url değil", "unknown", "", "", false, false, true},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			p, err := s.ParseURL(c.raw)
			if c.wantErr {
				if err == nil {
					t.Fatalf("hata bekleniyordu")
				}
				return
			}
			if err != nil {
				t.Fatalf("beklenmeyen hata: %v", err)
			}
			if p.Kind != c.kind || p.VideoID != c.video || p.ListID != c.list || p.Ambiguous != c.ambiguous || p.IsMix != c.mix {
				t.Fatalf("uyuşmazlık: %+v", p)
			}
		})
	}
}
"""

GO_FILES["services/download.go"] = r"""// ytdlp-studio:generated v1
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

	"__MODULE__/internal/engine"
	"__MODULE__/internal/model"
)

type TaskProgress struct {
	TaskID   string  `json:"taskId"`
	State    string  `json:"state"`
	Percent  float64 `json:"percent"`
	Speed    float64 `json:"speedBps"`
	ETA      float64 `json:"etaSec"`
	Error    string  `json:"error,omitempty"`
	FilePath string  `json:"filePath,omitempty"`
}

type downloadTask struct {
	id    string
	entry model.MediaEntry
	opts  model.DownloadOptions
}

type DownloadService struct {
	mu       sync.Mutex
	queue    chan downloadTask
	cancels  map[string]context.CancelFunc
	canceled map[string]bool
	tasks    map[string]downloadTask
	seq      int
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
	for _, e := range entries {
		d.seq++
		id := fmt.Sprintf("%s-%d", e.ID, d.seq)
		t := downloadTask{id: id, entry: e, opts: opts}
		d.tasks[id] = t
		staged = append(staged, t)
		ids = append(ids, id)
	}
	d.mu.Unlock()
	for _, t := range staged {
		d.queue <- t
		d.emit(TaskProgress{TaskID: t.id, State: "queued"})
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
	d.emit(TaskProgress{TaskID: taskID, State: "queued"})
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
	cmd := engine.BuildCommand(t.opts).ProgressFunc(300*time.Millisecond, func(p ytdlp.ProgressUpdate) {
		fm.Lock()
		if p.Filename != "" {
			lastFile = p.Filename
		}
		fm.Unlock()
		total := p.TotalBytes
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
		d.emit(TaskProgress{TaskID: t.id, State: state, Percent: pct, Speed: p.Speed, ETA: p.ETA.Seconds()})
	})

	d.emit(TaskProgress{TaskID: t.id, State: "downloading"})
	_, err := cmd.Run(ctx, t.entry.URL)

	d.mu.Lock()
	wasCanceled := d.canceled[t.id]
	d.mu.Unlock()
	switch {
	case wasCanceled || ctx.Err() != nil:
		d.emit(TaskProgress{TaskID: t.id, State: "canceled"})
	case err != nil:
		d.emit(TaskProgress{TaskID: t.id, State: "error", Error: err.Error()})
	default:
		fm.Lock()
		fp := lastFile
		fm.Unlock()
		if t.opts.Mode == "audio" && fp != "" {
			fp = strings.TrimSuffix(fp, filepath.Ext(fp)) + "." + t.opts.AudioFormat
		}
		d.emit(TaskProgress{TaskID: t.id, State: "done", Percent: 100, FilePath: fp})
	}
}

func (d *DownloadService) emit(p TaskProgress) {
	if app := application.Get(); app != nil {
		app.Event.Emit("task:progress", p)
	}
}
"""

GO_FILES["services/deps.go"] = r"""// ytdlp-studio:generated v1
package services

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"time"

	"github.com/lrstanley/go-ytdlp"
	"github.com/wailsapp/wails/v3/pkg/application"

	"__MODULE__/internal/engine"
)

type DepStatus struct {
	YtDlp     bool     `json:"ytDlp"`
	FFmpeg    bool     `json:"ffmpeg"`
	FFprobe   bool     `json:"ffprobe"`
	JSRuntime string   `json:"jsRuntime"`
	Missing   []string `json:"missing"`
}

type DepsService struct{}

func NewDepsService() *DepsService { return &DepsService{} }

func look(name string) string {
	if p, err := exec.LookPath(name); err == nil {
		return p
	}
	dirs := []string{"/opt/homebrew/bin", "/usr/local/bin"}
	if cache, err := ytdlp.GetCacheDir(); err == nil {
		dirs = append(dirs, cache)
	}
	for _, dir := range dirs {
		p := filepath.Join(dir, name)
		if st, err := os.Stat(p); err == nil && !st.IsDir() {
			return p
		}
	}
	return ""
}

func (s *DepsService) CheckDeps() DepStatus {
	yt, ff, fp := look("yt-dlp"), look("ffmpeg"), look("ffprobe")
	js := ""
	if look("deno") != "" {
		js = "deno"
	} else if look("bun") != "" {
		js = "bun"
	}
	st := DepStatus{YtDlp: yt != "", FFmpeg: ff != "", FFprobe: fp != "", JSRuntime: js, Missing: []string{}}
	if !st.YtDlp {
		st.Missing = append(st.Missing, "yt-dlp")
	}
	if !st.FFmpeg {
		st.Missing = append(st.Missing, "ffmpeg")
	}
	if !st.FFprobe {
		st.Missing = append(st.Missing, "ffprobe")
	}
	if js == "" {
		st.Missing = append(st.Missing, "deno/bun")
	}
	ffDir := ""
	if ff != "" {
		ffDir = filepath.Dir(ff)
	}
	engine.SetPaths(yt, ffDir)
	if app := application.Get(); app != nil {
		app.Event.Emit("deps:status", st)
	}
	return st
}

func safeInstall(fn func()) (err error) {
	defer func() {
		if r := recover(); r != nil {
			err = fmt.Errorf("%v", r)
		}
	}()
	fn()
	return nil
}

func (s *DepsService) InstallDeps() (DepStatus, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Minute)
	defer cancel()
	st := s.CheckDeps()
	if !st.YtDlp {
		if err := safeInstall(func() { ytdlp.MustInstall(ctx, nil) }); err != nil {
			return s.CheckDeps(), fmt.Errorf("yt-dlp kurulumu başarısız: %w", err)
		}
	}
	if !st.FFmpeg {
		if err := safeInstall(func() { ytdlp.MustInstallFFmpeg(ctx, nil) }); err != nil {
			return s.CheckDeps(), fmt.Errorf("ffmpeg kurulumu başarısız: %w", err)
		}
	}
	if !st.FFprobe {
		if err := safeInstall(func() { ytdlp.MustInstallFFprobe(ctx, nil) }); err != nil {
			return s.CheckDeps(), fmt.Errorf("ffprobe kurulumu başarısız: %w", err)
		}
	}
	if st.JSRuntime == "" {
		if err := safeInstall(func() { ytdlp.MustInstallBun(ctx, nil) }); err != nil {
			return s.CheckDeps(), fmt.Errorf("bun kurulumu başarısız: %w", err)
		}
	}
	return s.CheckDeps(), nil
}

func (s *DepsService) UpdateYtDlp() (string, error) {
	yt := look("yt-dlp")
	if yt == "" {
		return "", fmt.Errorf("yt-dlp bulunamadı; önce bileşenleri kurun")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()
	out, err := exec.CommandContext(ctx, yt, "-U").CombinedOutput()
	s.CheckDeps()
	return string(out), err
}
"""

GO_FILES["services/settings.go"] = r"""// ytdlp-studio:generated v1
package services

import (
	"encoding/json"
	"os"
	"path/filepath"

	"__MODULE__/internal/model"
)

type SettingsService struct{}

func NewSettingsService() *SettingsService { return &SettingsService{} }

func settingsPath() (string, error) {
	base, err := os.UserConfigDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(base, "ytdlp-studio", "settings.json"), nil
}

func (s *SettingsService) Load() model.DownloadOptions {
	o := model.DefaultOptions()
	p, err := settingsPath()
	if err != nil {
		return o
	}
	data, err := os.ReadFile(p)
	if err != nil {
		return o
	}
	_ = json.Unmarshal(data, &o)
	return o
}

func (s *SettingsService) Save(o model.DownloadOptions) error {
	if err := model.Validate(o); err != nil {
		return err
	}
	p, err := settingsPath()
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(o, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(p, data, 0o644)
}
"""

GO_FILES["services/events.go"] = r"""// ytdlp-studio:generated v1
package services

import "github.com/wailsapp/wails/v3/pkg/application"

func init() {
	application.RegisterEvent[TaskProgress]("task:progress")
	application.RegisterEvent[DepStatus]("deps:status")
}
"""

TS_FILES["frontend/src/types.ts"] = r"""// ytdlp-studio:generated v1
export interface ParsedURL {
  kind: "video" | "playlist" | "unknown";
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
  entries: MediaEntry[];
}

export interface DownloadOptions {
  mode: "audio" | "video";
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
  state: "queued" | "downloading" | "converting" | "done" | "error" | "canceled";
  percent: number;
  speedBps: number;
  etaSec: number;
  error?: string;
  filePath?: string;
}

export interface DepStatus {
  ytDlp: boolean;
  ffmpeg: boolean;
  ffprobe: boolean;
  jsRuntime: string;
  missing: string[];
}
"""

TS_FILES["frontend/src/api.ts"] = r"""// ytdlp-studio:generated v1
// Binding import yolu 02_validate.py tarafından doğrulanır ve gerekirse düzeltilir.
import { AnalyzeService, DepsService, DownloadService, SettingsService } from "../bindings/__MODULE__/services";

export { AnalyzeService, DepsService, DownloadService, SettingsService };
"""

TS_FILES["frontend/src/store.ts"] = r"""// ytdlp-studio:generated v1
import { create } from "zustand";
import type { DepStatus, DownloadOptions, MediaInfo, ParsedURL } from "./types";

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
  set: (p: Partial<AppState>) => void;
}

export const useStore = create<AppState>((set) => ({
  url: "",
  scope: "video",
  selected: new Set<string>(),
  options: DEFAULT_OPTIONS,
  analyzing: false,
  installing: false,
  tab: "analyze",
  set: (p) => set(p),
}));
"""

TS_FILES["frontend/src/taskStore.ts"] = r"""// ytdlp-studio:generated v1
import { create } from "zustand";
import type { MediaEntry, TaskProgress } from "./types";

export interface TaskItem extends TaskProgress {
  title: string;
}

interface TaskState {
  tasks: Record<string, TaskItem>;
  order: string[];
  addMany: (ids: string[], entries: MediaEntry[]) => void;
  upsert: (p: TaskProgress) => void;
  clearFinished: () => void;
}

export const useTasks = create<TaskState>((set) => ({
  tasks: {},
  order: [],
  addMany: (ids, entries) =>
    set((s) => {
      const tasks = { ...s.tasks };
      const order = [...s.order];
      ids.forEach((id, i) => {
        const e = entries[i];
        tasks[id] = { taskId: id, title: e ? e.title : id, state: "queued", percent: 0, speedBps: 0, etaSec: 0 };
        order.push(id);
      });
      return { tasks, order };
    }),
  upsert: (p) =>
    set((s) => {
      const prev = s.tasks[p.taskId];
      const base: TaskItem = prev ?? { taskId: p.taskId, title: "", state: "queued", percent: 0, speedBps: 0, etaSec: 0 };
      const item: TaskItem = { ...base, ...p, error: p.state === "error" ? p.error : undefined };
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
"""

TS_FILES["frontend/src/components/PasteBar.tsx"] = r"""// ytdlp-studio:generated v1
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
        info,
        selected: new Set(info.entries.filter((e) => e.available).map((e) => e.id)),
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
      <button onClick={() => void analyze(url, scope)} disabled={analyzing || !url.trim()}>
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
      {parsed?.isMix && <span className="warn">⚠ Mix listesi sonsuzdur; ilk öğelerle sınırlı olabilir</span>}
      {error && <div className="error">{error}</div>}
    </section>
  );
}
"""

TS_FILES["frontend/src/components/PreviewList.tsx"] = r"""// ytdlp-studio:generated v1
import { useState } from "react";
import { useStore } from "../store";

function fmtDuration(sec: number): string {
  if (!sec || sec <= 0) return "—";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return m + ":" + String(s).padStart(2, "0");
}

export function PreviewList() {
  const info = useStore((s) => s.info);
  const selected = useStore((s) => s.selected);
  const set = useStore((s) => s.set);
  const [filter, setFilter] = useState("");

  if (!info) {
    return <section className="preview empty">URL yapıştırdığında içerik önizlemesi burada görünür.</section>;
  }

  const visible = info.entries.filter((e) => e.title.toLowerCase().includes(filter.toLowerCase()));
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
      <div className="preview-head">
        <label className="select-all">
          <input type="checkbox" checked={allSelected} onChange={toggleAll} />
          <b>{info.title}</b>
        </label>
        <input className="filter" placeholder="Ara…" value={filter} onChange={(e) => setFilter(e.target.value)} />
        <span className="count">
          {selected.size}/{info.entries.length}
        </span>
      </div>
      <div className="rows">
        {visible.map((e) => (
          <label key={e.id} className={e.available ? "row" : "row unavailable"}>
            <input type="checkbox" checked={selected.has(e.id)} disabled={!e.available} onChange={() => toggle(e.id)} />
            {e.thumbnail ? <img src={e.thumbnail} loading="lazy" alt="" /> : <div className="thumb-placeholder" />}
            <span className="idx">{String(e.index).padStart(3, "0")}</span>
            <span className="title">{e.title}</span>
            <span className="dur">{fmtDuration(e.durationSec)}</span>
          </label>
        ))}
      </div>
    </section>
  );
}
"""

TS_FILES["frontend/src/components/OptionsPanel.tsx"] = r"""// ytdlp-studio:generated v1
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
      <h3>İndirme Kuralları</h3>
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
          <button onClick={() => void pickFolder()}>Seç…</button>
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
        <input type="checkbox" checked={options.embedThumbnail} onChange={(e) => upd({ embedThumbnail: e.target.checked })} />
        Kapak göm
      </label>
      <label className="check">
        <input type="checkbox" checked={options.embedMetadata} onChange={(e) => upd({ embedMetadata: e.target.checked })} />
        Metadata göm
      </label>

      <details>
        <summary>Gelişmiş</summary>
        <label>
          Hız limiti
          <input placeholder="ör. 5M (boş = limitsiz)" value={options.rateLimit} onChange={(e) => upd({ rateLimit: e.target.value })} />
        </label>
        <label>
          Eşzamanlı parça
          <select value={options.concurrentFragments} onChange={(e) => upd({ concurrentFragments: Number(e.target.value) })}>
            {[1, 2, 4, 8].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <label>
          Çerezler
          <select value={options.cookiesBrowser} onChange={(e) => upd({ cookiesBrowser: e.target.value })}>
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
"""

TS_FILES["frontend/src/components/DownloadButton.tsx"] = r"""// ytdlp-studio:generated v1
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
      addMany(ids, entries);
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
"""

TS_FILES["frontend/src/components/QueuePanel.tsx"] = r"""// ytdlp-studio:generated v1
import { DownloadService } from "../api";
import { useTasks } from "../taskStore";

function fmtSpeed(bps: number): string {
  if (!bps || bps <= 0) return "";
  return (bps / (1024 * 1024)).toFixed(1) + " MB/s";
}

const STATE_LABEL: Record<string, string> = {
  queued: "Sırada",
  downloading: "İndiriliyor",
  converting: "Dönüştürülüyor",
  done: "Tamamlandı",
  error: "Hata",
  canceled: "İptal",
};

export function QueuePanel() {
  const tasks = useTasks((s) => s.tasks);
  const order = useTasks((s) => s.order);
  const clearFinished = useTasks((s) => s.clearFinished);

  if (order.length === 0) {
    return <section className="preview empty">Kuyruk boş. Analiz sekmesinden indirme başlat.</section>;
  }

  return (
    <section className="queue-panel">
      <div className="preview-head">
        <b>Kuyruk ({order.length})</b>
        <button className="ghost" onClick={clearFinished}>
          Bitenleri temizle
        </button>
      </div>
      <div className="rows">
        {order.map((id) => {
          const t = tasks[id];
          if (!t) return null;
          const active = t.state === "queued" || t.state === "downloading" || t.state === "converting";
          return (
            <div key={id} className="task">
              <div className="task-line">
                <span className="title">{t.title || id}</span>
                <span className={"badge " + t.state}>{STATE_LABEL[t.state] ?? t.state}</span>
                {t.state === "downloading" && (
                  <span className="meta">
                    {fmtSpeed(t.speedBps)}
                    {t.etaSec > 0 ? " · " + Math.ceil(t.etaSec) + " sn" : ""}
                  </span>
                )}
                {active && (
                  <button className="ghost" onClick={() => void DownloadService.Cancel(id)}>
                    İptal
                  </button>
                )}
                {(t.state === "error" || t.state === "canceled") && (
                  <button className="ghost" onClick={() => void DownloadService.Retry(id)}>
                    Yeniden
                  </button>
                )}
                {t.state === "done" && (
                  <button className="ghost" onClick={() => void DownloadService.Reveal(t.filePath ?? "")}>
                    Finder'da göster
                  </button>
                )}
              </div>
              <div className="bar">
                <div className="fill" style={{ width: Math.min(100, Math.max(0, t.percent)) + "%" }} />
              </div>
              {t.error && <div className="error small">{t.error}</div>}
            </div>
          );
        })}
      </div>
    </section>
  );
}
"""

TS_FILES["frontend/src/index.css"] = r"""/* ytdlp-studio:generated v1 */
:root { color-scheme: dark; --bg:#0f1115; --panel:#161a22; --line:#232a36; --text:#e6e9ef; --muted:#8b93a3; --accent:#3b82f6; --ok:#22c55e; --err:#ef4444; --warn:#f59e0b; }
* { box-sizing: border-box; }
html, body, #root { height: 100%; margin: 0; }
body { background: var(--bg); color: var(--text); font: 14px/1.45 -apple-system, "SF Pro Text", system-ui, sans-serif; }
.app { display: flex; flex-direction: column; height: 100%; }
.topbar { display: flex; align-items: center; gap: 16px; padding: 10px 16px; border-bottom: 1px solid var(--line); background: var(--panel); }
.brand { font-weight: 700; }
.tabs { display: flex; gap: 6px; }
.tab { background: none; border: 1px solid transparent; color: var(--muted); padding: 6px 12px; border-radius: 8px; cursor: pointer; }
.tab.active { color: var(--text); border-color: var(--line); background: var(--bg); }
.topbar-actions { margin-left: auto; }
button { background: var(--accent); color: #fff; border: 0; padding: 7px 12px; border-radius: 8px; cursor: pointer; font-size: 13px; }
button:disabled { opacity: .45; cursor: default; }
button.ghost { background: transparent; border: 1px solid var(--line); color: var(--text); }
.banner { display: flex; gap: 12px; align-items: center; padding: 8px 16px; background: #2a2113; border-bottom: 1px solid var(--warn); color: var(--warn); }
.notice { padding: 6px 16px; color: var(--muted); border-bottom: 1px solid var(--line); cursor: pointer; white-space: pre-wrap; }
.analyze { display: flex; flex-direction: column; gap: 12px; padding: 14px 16px; flex: 1; min-height: 0; }
.pastebar { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.url-input { flex: 1; min-width: 260px; background: var(--panel); border: 1px solid var(--line); color: var(--text); padding: 9px 12px; border-radius: 10px; }
.pastebar select { background: var(--panel); border: 1px solid var(--line); color: var(--text); border-radius: 8px; padding: 7px 8px; }
.chip { font-size: 12px; color: var(--muted); border: 1px solid var(--line); padding: 3px 8px; border-radius: 999px; }
.warn { color: var(--warn); font-size: 12px; }
.error { color: var(--err); font-size: 12px; width: 100%; white-space: pre-wrap; }
.error.small { font-size: 11px; }
.analyze-grid { display: grid; grid-template-columns: 1fr 300px; gap: 14px; flex: 1; min-height: 0; }
.preview { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
.preview.empty { align-items: center; justify-content: center; color: var(--muted); padding: 24px; }
.preview-head { display: flex; gap: 10px; align-items: center; padding: 10px 12px; border-bottom: 1px solid var(--line); }
.select-all { display: flex; gap: 8px; align-items: center; flex: 1; min-width: 0; }
.select-all b { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.filter { background: var(--bg); border: 1px solid var(--line); color: var(--text); border-radius: 8px; padding: 5px 8px; width: 140px; }
.count { color: var(--muted); font-size: 12px; }
.rows { overflow-y: auto; flex: 1; }
.row { display: flex; gap: 10px; align-items: center; padding: 6px 12px; cursor: pointer; }
.row:hover { background: #1b2130; }
.row img, .thumb-placeholder { width: 72px; height: 40px; object-fit: cover; border-radius: 6px; background: #0b0d11; flex: none; }
.row .idx { color: var(--muted); font-size: 11px; width: 28px; flex: none; }
.row .title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.row .dur { color: var(--muted); font-size: 12px; flex: none; }
.row.unavailable { opacity: .4; pointer-events: none; }
.options { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 12px; display: flex; flex-direction: column; gap: 10px; overflow-y: auto; }
.options h3 { margin: 0 0 2px; font-size: 13px; }
.options label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }
.options label.check { flex-direction: row; align-items: center; gap: 8px; color: var(--text); }
.options select, .options input { background: var(--bg); border: 1px solid var(--line); color: var(--text); border-radius: 8px; padding: 6px 8px; font-size: 13px; }
.seg { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.seg button { background: var(--bg); border: 1px solid var(--line); color: var(--muted); }
.seg button.active { background: var(--accent); color: #fff; border-color: var(--accent); }
.folder-row { display: flex; gap: 6px; }
.folder-row input { flex: 1; min-width: 0; }
.options details { display: flex; flex-direction: column; gap: 8px; }
.options details summary { cursor: pointer; color: var(--muted); font-size: 12px; }
.actionbar { display: flex; justify-content: flex-end; }
.download { font-size: 14px; padding: 10px 18px; }
.queue { flex: 1; min-height: 0; padding: 14px 16px; display: flex; }
.queue-panel { flex: 1; background: var(--panel); border: 1px solid var(--line); border-radius: 12px; display: flex; flex-direction: column; min-height: 0; overflow: hidden; }
.task { padding: 8px 12px; border-bottom: 1px solid var(--line); display: flex; flex-direction: column; gap: 6px; }
.task-line { display: flex; gap: 10px; align-items: center; }
.task-line .title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.meta { color: var(--muted); font-size: 12px; }
.badge { font-size: 11px; padding: 2px 8px; border-radius: 999px; border: 1px solid var(--line); color: var(--muted); }
.badge.downloading, .badge.converting { color: var(--accent); border-color: var(--accent); }
.badge.done { color: var(--ok); border-color: var(--ok); }
.badge.error { color: var(--err); border-color: var(--err); }
.bar { height: 5px; background: var(--bg); border-radius: 999px; overflow: hidden; }
.fill { height: 100%; background: var(--accent); transition: width .25s; }
"""

MAIN_GO = r"""// ytdlp-studio:generated v1
package main

import (
	"embed"
	"log"

	"github.com/wailsapp/wails/v3/pkg/application"

	"__MODULE__/services"
)

//go:embed frontend/dist
var assets embed.FS

func main() {
	deps := services.NewDepsService()
	download := services.NewDownloadService(3)
	settings := services.NewSettingsService()
	analyze := &services.AnalyzeService{}

	app := application.New(application.Options{
		Name: "ytdlp-studio",
		Services: []application.Service{
			application.NewService(analyze),
			application.NewService(download),
			application.NewService(settings),
			application.NewService(deps),
		},
		Assets: application.AssetOptions{
			Handler: application.AssetFileServerFS(assets),
		},
	})

	app.NewWebviewWindowWithOptions(application.WebviewWindowOptions{
		Title:  "ytdlp-studio",
		Width:  1180,
		Height: 760,
		URL:    "/",
	})

	go deps.CheckDeps()

	if err := app.Run(); err != nil {
		log.Fatal(err)
	}
}
"""

APP_TSX = r"""// ytdlp-studio:generated v1
import { useEffect } from "react";
import { Events } from "@wailsio/runtime";
import { DepsService, SettingsService } from "./api";
import { useStore } from "./store";
import { useTasks } from "./taskStore";
import type { DepStatus, TaskProgress } from "./types";
import { PasteBar } from "./components/PasteBar";
import { PreviewList } from "./components/PreviewList";
import { OptionsPanel } from "./components/OptionsPanel";
import { DownloadButton } from "./components/DownloadButton";
import { QueuePanel } from "./components/QueuePanel";

export default function App() {
  const tab = useStore((s) => s.tab);
  const deps = useStore((s) => s.deps);
  const installing = useStore((s) => s.installing);
  const notice = useStore((s) => s.notice);
  const set = useStore((s) => s.set);
  const upsert = useTasks((s) => s.upsert);

  useEffect(() => {
    const offProgress = Events.On("task:progress", (ev) => upsert(ev.data as TaskProgress));
    const offDeps = Events.On("deps:status", (ev) => set({ deps: ev.data as DepStatus }));
    return () => {
      offProgress();
      offDeps();
    };
  }, [upsert, set]);

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

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">ytdlp-studio</div>
        <nav className="tabs">
          <button className={tab === "analyze" ? "tab active" : "tab"} onClick={() => set({ tab: "analyze" })}>
            Analiz
          </button>
          <button className={tab === "queue" ? "tab active" : "tab"} onClick={() => set({ tab: "queue" })}>
            Kuyruk
          </button>
        </nav>
        <div className="topbar-actions">
          <button className="ghost" onClick={() => void updateYtDlp()}>
            yt-dlp Güncelle
          </button>
        </div>
      </header>

      {missing.length > 0 && (
        <div className="banner">
          <span>Eksik bileşenler: {missing.join(", ")}</span>
          <button onClick={() => void installDeps()} disabled={installing}>
            {installing ? "Kuruluyor…" : "Otomatik Kur"}
          </button>
        </div>
      )}
      {notice && (
        <div className="notice" onClick={() => set({ notice: undefined })}>
          {notice}
        </div>
      )}

      {tab === "analyze" ? (
        <main className="analyze">
          <PasteBar />
          <div className="analyze-grid">
            <PreviewList />
            <OptionsPanel />
          </div>
          <footer className="actionbar">
            <DownloadButton />
          </footer>
        </main>
      ) : (
        <main className="queue">
          <QueuePanel />
        </main>
      )}
    </div>
  );
}
"""

MAIN_TSX = r"""// ytdlp-studio:generated v1
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
"""

DIST_PLACEHOLDER = """<!doctype html>
<!-- ytdlp-studio:generated v1 -->
<html><head><meta charset="utf-8"><title>ytdlp-studio</title></head>
<body><div id="root"></div><p>frontend build bekleniyor…</p></body></html>
"""


def ensure_module(root, report):
    gomod = read(root / "go.mod")
    m = re.search(r"(?m)^module\s+(\S+)", gomod)
    if not m:
        die("ERROR:\ngo.mod içinde module satırı bulunamadı.")
    module = m.group(1)
    if module == "changeme":
        run(["go", "mod", "edit", "-module", "ytdlp-studio"], cwd=root)
        if not re.search(r"(?m)^module\s+ytdlp-studio$", read(root / "go.mod")):
            die("ERROR:\ngo.mod modül adı değiştirilemedi.")
        module = "ytdlp-studio"
        report.modified.append("go.mod (module: changeme → ytdlp-studio)")
    return module


def update_package_json(root, report):
    p = root / "frontend" / "package.json"
    pkg = json.loads(read(p))
    deps = pkg.setdefault("dependencies", {})
    if "react" not in deps or "react-dom" not in deps:
        die("ERROR:\nfrontend/package.json beklenen React yapısında değil (react/react-dom yok).")
    added = []
    if "zustand" not in deps:
        deps["zustand"] = "^5.0.0"
        added.append("zustand@^5.0.0")
    if "@wailsio/runtime" not in deps:
        deps["@wailsio/runtime"] = "latest"
        added.append("@wailsio/runtime@latest")
    if added:
        write_verified(p, json.dumps(pkg, indent=2) + "\n")
        check = json.loads(read(p))
        for a in added:
            name = a.rsplit("@", 1)[0]
            if name not in check["dependencies"]:
                die(f"package.json doğrulaması başarısız: {name}")
        report.modified.append("frontend/package.json (dependencies: " + ", ".join(added) + ")")
    else:
        report.skipped.append("frontend/package.json (dependencies zaten tam)")


def frontend_refs(root, needle):
    hits = []
    src = root / "frontend" / "src"
    for p in src.rglob("*"):
        if p.is_file() and p.suffix in (".ts", ".tsx", ".css", ".html"):
            if needle in read(p):
                hits.append(str(p.relative_to(root)))
    idx = root / "frontend" / "index.html"
    if idx.is_file() and needle in read(idx):
        hits.append("frontend/index.html")
    return hits


def remove_legacy(root, report):
    # 1) Şablon greet servisi: yalnızca hiçbir Go dosyası referans etmiyorsa sil.
    for p in sorted(root.glob("*.go")):
        if p.name == "main.go" or "GreetService" not in read(p):
            continue
        refs = []
        for other in root.rglob("*.go"):
            if other == p:
                continue
            if any(part in ("node_modules", "dist", "bindings") for part in other.parts):
                continue
            if "GreetService" in read(other):
                refs.append(str(other.relative_to(root)))
        if refs:
            report.notes.append(f"GreetService hâlâ referanslı ({refs}) → {p.name} silinmedi")
            continue
        delete_file(root, str(p.relative_to(root)), "GreetService", report)

    # 2) Kullanılmayan şablon CSS dosyaları.
    for rel in ("frontend/src/App.css", "frontend/src/style.css"):
        p = root / rel
        if not p.exists():
            report.skipped.append(rel + " (zaten yok)")
            continue
        refs = frontend_refs(root, p.name)
        if refs:
            report.notes.append(f"{rel} hâlâ referanslı ({refs}) → silinmedi")
            continue
        delete_file(root, rel, None, report)

    # 3) Kullanılmayan şablon görselleri.
    assets = root / "frontend" / "src" / "assets"
    if assets.exists():
        refs = frontend_refs(root, "assets/")
        if refs:
            report.notes.append(f"assets/ hâlâ referanslı ({refs}) → silinmedi")
        else:
            shutil.rmtree(assets)
            if assets.exists():
                die("assets silme doğrulaması başarısız")
            report.deleted.append("frontend/src/assets/ (kullanılmayan şablon görselleri)")
    else:
        report.skipped.append("frontend/src/assets/ (zaten yok)")


def main():
    args = base_parser("ytdlp-studio değişiklik uygulayıcı").parse_args()
    root = find_root(args.root)
    report = Report()
    print("PROJECT_ROOT =", root)

    if "github.com/wailsapp/wails/v3" not in read(root / "go.mod"):
        die("ERROR:\ngo.mod içinde wails/v3 yok — bu otomasyon v3 içindir. Değişiklik yapılmadı.")

    module = ensure_module(root, report)

    # 1) Yeni backend + frontend dosyaları
    for rel, tpl in GO_FILES.items():
        write_generated(root, rel, tpl.replace("__MODULE__", module), report)
    for rel, tpl in TS_FILES.items():
        write_generated(root, rel, tpl.replace("__MODULE__", module), report)

    # 2) Şablon dosyalarını doğrulamalı değiştir
    replace_file(root, "main.go", MAIN_GO.replace("__MODULE__", module),
                 ["github.com/wailsapp/wails/v3/pkg/application", "//go:embed frontend/dist"], report)
    replace_file(root, "frontend/src/App.tsx", APP_TSX, ["function App", "export default"], report)
    replace_file(root, "frontend/src/main.tsx", MAIN_TSX, ["createRoot", "ReactDOM"], report)

    # 3) index.html title patch
    patch_title(root, report)

    # 4) go:embed için dist placeholder (vite build sonra üzerine yazar)
    dist_index = root / "frontend" / "dist" / "index.html"
    if dist_index.exists():
        report.skipped.append("frontend/dist/index.html (mevcut)")
    else:
        write_verified(dist_index, DIST_PLACEHOLDER)
        report.created.append("frontend/dist/index.html (go:embed placeholder)")

    # 5) Dependency değişiklikleri
    update_package_json(root, report)
    run(["go", "get", "github.com/lrstanley/go-ytdlp@latest"], cwd=root)
    if "github.com/lrstanley/go-ytdlp" not in read(root / "go.mod"):
        die("ERROR:\ngo-ytdlp go.mod'a eklenemedi.")
    report.modified.append("go.mod/go.sum (github.com/lrstanley/go-ytdlp eklendi)")

    # 6) Legacy/ölü kod temizliği
    remove_legacy(root, report)

    # 7) Son doğrulama
    expected = list(GO_FILES) + list(TS_FILES) + ["main.go", "frontend/src/App.tsx", "frontend/src/main.tsx"]
    for rel in expected:
        if not (root / rel).is_file():
            die(f"ERROR:\nBeklenen dosya oluşmadı: {rel}")
    if "services.NewDownloadService" not in read(root / "main.go"):
        die("ERROR:\nmain.go servis kaydı doğrulaması başarısız.")
    report.notes.append("Entegrasyon: 4 servis main.go'da kayıtlı; task:progress + deps:status event'leri bağlı")
    report.notes.append("Entegrasyon: URL parse → flat-playlist önizleme → kurallı indirme kuyruğu uçtan uca bağlı")

    report.summary("UPDATE SUMMARY (apply)")
    print("\nSonraki adım: python3 scripts/02_validate.py")


if __name__ == "__main__":
    guard_main(main)