// ytdlp-studio:generated v1
// ytdlp-studio:analyze v3
package services

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/url"
	"regexp"
	"sort"
	"strings"
	"sync"
	"time"

	"ytdlp-studio/internal/engine"
	"ytdlp-studio/internal/model"
)

type AnalyzeService struct {
	mu     sync.Mutex
	ctx    context.Context
	cancel context.CancelFunc
	wg     sync.WaitGroup
	closed bool
}

func NewAnalyzeService() *AnalyzeService {
	ctx, cancel := context.WithCancel(context.Background())
	return &AnalyzeService{ctx: ctx, cancel: cancel}
}

func (s *AnalyzeService) beginOperation(timeout time.Duration) (context.Context, func(), error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.closed {
		return nil, nil, errors.New("uygulama kapanıyor; analiz başlatılamaz")
	}
	if s.ctx == nil {
		s.ctx, s.cancel = context.WithCancel(context.Background())
	}
	ctx, cancel := context.WithTimeout(s.ctx, timeout)
	s.wg.Add(1)
	return ctx, func() { cancel(); s.wg.Done() }, nil
}

// Shutdown cancels metadata and subtitle extraction processes, then waits for
// all requests to release the shared yt-dlp operation gate.
func (s *AnalyzeService) shutdown(ctx context.Context) error {
	s.mu.Lock()
	s.closed = true
	if s.cancel != nil {
		s.cancel()
	}
	s.mu.Unlock()
	done := make(chan struct{})
	go func() { s.wg.Wait(); close(done) }()
	select {
	case <-done:
		return nil
	case <-ctx.Done():
		return ctx.Err()
	}
}

type SubtitleTrack struct {
	Lang string   `json:"lang"`
	Name string   `json:"name"`
	Exts []string `json:"exts"`
	Auto bool     `json:"auto"`
}

type SubtitleInfo struct {
	Manual []SubtitleTrack `json:"manual"`
	Auto   []SubtitleTrack `json:"auto"`
}

type rawInfo struct {
	Type       string     `json:"_type"`
	ID         string     `json:"id"`
	Title      string     `json:"title"`
	WebpageURL string     `json:"webpage_url"`
	URL        string     `json:"url"`
	Duration   float64    `json:"duration"`
	Entries    []*rawInfo `json:"entries"`
	Thumbnails []struct {
		URL string `json:"url"`
	} `json:"thumbnails"`
	PlaylistTitle string `json:"playlist_title"`
	PlaylistID    string `json:"playlist_id"`
	PlaylistIndex *int   `json:"playlist_index"`
	Availability  string `json:"availability"`
}

var (
	youtubeVideoIDPattern = regexp.MustCompile(`^[A-Za-z0-9_-]{11}$`)
	youtubeListIDPattern  = regexp.MustCompile(`^[A-Za-z0-9_-]+$`)
)

func (s *AnalyzeService) ParseURL(raw string) (model.ParsedURL, error) {
	p := model.ParsedURL{Kind: "unknown", CanonicalURL: strings.TrimSpace(raw)}
	u, err := url.Parse(p.CanonicalURL)
	if err != nil || !u.IsAbs() || u.Host == "" {
		return p, fmt.Errorf("geçersiz URL: %q", raw)
	}
	if !strings.EqualFold(u.Scheme, "https") || u.User != nil {
		return p, errors.New("YouTube bağlantıları HTTPS olmalı ve kullanıcı bilgisi içermemeli")
	}
	if port := u.Port(); port != "" && port != "443" {
		return p, errors.New("YouTube bağlantısında özel port kullanılamaz")
	}

	host := strings.ToLower(u.Hostname())
	host = strings.TrimPrefix(host, "www.")
	host = strings.TrimPrefix(host, "m.")
	isYouTube := host == "youtube.com" || host == "youtube-nocookie.com" ||
		host == "music.youtube.com" || host == "youtu.be"
	if !isYouTube {
		return p, nil
	}

	q := u.Query()
	p.VideoID, p.ListID = q.Get("v"), q.Get("list")
	if host == "youtu.be" {
		parts := strings.Split(strings.Trim(u.Path, "/"), "/")
		if len(parts) > 0 {
			p.VideoID = parts[0]
		}
	} else {
		parts := strings.Split(strings.Trim(u.Path, "/"), "/")
		if len(parts) >= 2 && (parts[0] == "shorts" || parts[0] == "live" || parts[0] == "embed") {
			p.VideoID = parts[1]
		}
	}
	if !youtubeVideoIDPattern.MatchString(p.VideoID) {
		p.VideoID = ""
	}
	if !youtubeListIDPattern.MatchString(p.ListID) {
		p.ListID = ""
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

func flatten(in []*rawInfo, depth int, out *[]*rawInfo) {
	for _, r := range in {
		if r == nil {
			continue
		}
		if len(r.Entries) == 0 || depth > 8 {
			*out = append(*out, r)
			continue
		}
		flatten(r.Entries, depth+1, out)
	}
}

func unavailable(title, availability string) bool {
	t := strings.ToLower(title)
	if title == "" {
		return true
	}
	if strings.Contains(t, "[private video]") || strings.Contains(t, "[deleted video]") ||
		strings.Contains(t, "[unavailable") {
		return true
	}
	switch availability {
	case "private", "premium_only", "subscriber_only", "needs_auth":
		return true
	}
	return false
}

func thumbOf(r *rawInfo) string {
	for i := len(r.Thumbnails) - 1; i >= 0; i-- {
		if r.Thumbnails[i].URL != "" {
			return r.Thumbnails[i].URL
		}
	}
	if len(r.ID) == 11 {
		return "https://i.ytimg.com/vi/" + r.ID + "/hqdefault.jpg"
	}
	return ""
}

func (s *AnalyzeService) Analyze(raw, scope, playlistItems string) (*model.MediaInfo, error) {
	p, err := s.ParseURL(raw)
	if err != nil {
		return nil, err
	}
	if p.Kind == "unknown" {
		return nil, errors.New("desteklenmeyen bağlantı: YouTube video veya playlist URL'si gerekli")
	}
	reverse := strings.HasSuffix(scope, "-reverse")
	if reverse {
		scope = strings.TrimSuffix(scope, "-reverse")
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

	ctx, endOperation, opErr := s.beginOperation(10 * time.Minute)
	if opErr != nil {
		return nil, opErr
	}
	defer endOperation()

	release, gateErr := acquireToolRead(ctx)
	if gateErr != nil {
		return nil, gateErr
	}
	var data []byte
	func() {
		defer release()
		data, err = engine.ExtractInfo(ctx, target, engine.AnalyzeArgs(target, playlistItems, reverse)...)
	}()
	if err != nil {
		return nil, fmt.Errorf("içerik analizi başarısız: %w", err)
	}
	var root rawInfo
	if err := json.Unmarshal(data, &root); err != nil {
		return nil, fmt.Errorf("analiz çıktısı çözümlenemedi: %w", err)
	}

	var flat []*rawInfo
	flatten([]*rawInfo{&root}, 0, &flat)

	seen := map[string]bool{}
	var entries []*rawInfo
	for _, r := range flat {
		key := r.ID + "|" + r.WebpageURL
		if r.ID != "" && seen[key] {
			continue
		}
		seen[key] = true
		entries = append(entries, r)
	}
	if len(entries) == 0 {
		return nil, errors.New("içerik bulunamadı")
	}

	out := &model.MediaInfo{Kind: "video", ID: p.VideoID, Title: root.Title}
	if wantPlaylist || len(root.Entries) > 0 || len(entries) > 1 {
		out.Kind = "playlist"
		out.ID = p.ListID
		if out.ID == "" {
			out.ID = root.PlaylistID
		}
		if root.Title != "" {
			out.Title = root.Title
		} else if root.PlaylistTitle != "" {
			out.Title = root.PlaylistTitle
		}
	}
	if out.Title == "" {
		out.Title = entries[0].Title
	}
	if out.Title == "" {
		out.Title = out.ID
	}

	for i, r := range entries {
		idx := i + 1
		if r.PlaylistIndex != nil && *r.PlaylistIndex > 0 {
			idx = *r.PlaylistIndex
		}
		title := r.Title
		if title == "" {
			title = r.ID
		}
		link := r.WebpageURL
		if link == "" && strings.HasPrefix(r.URL, "http") {
			link = r.URL
		}
		if link == "" && r.ID != "" {
			link = "https://www.youtube.com/watch?v=" + r.ID
		}
		out.Entries = append(out.Entries, model.MediaEntry{
			ID:          r.ID,
			URL:         link,
			Title:       title,
			DurationSec: r.Duration,
			Thumbnail:   thumbOf(r),
			Index:       idx,
			Available:   r.ID != "" && !unavailable(r.Title, r.Availability),
		})
	}
	return out, nil
}

func tracks(m map[string][]struct {
	Ext  string `json:"ext"`
	Name string `json:"name"`
}, auto bool) []SubtitleTrack {
	var out []SubtitleTrack
	for lang, formats := range m {
		t := SubtitleTrack{Lang: lang, Auto: auto}
		exts := map[string]bool{}
		for _, f := range formats {
			if f.Name != "" {
				t.Name = f.Name
			}
			if f.Ext != "" {
				exts[f.Ext] = true
			}
		}
		for e := range exts {
			t.Exts = append(t.Exts, e)
		}
		sort.Strings(t.Exts)
		if t.Name == "" {
			t.Name = lang
		}
		out = append(out, t)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Lang < out[j].Lang })
	return out
}

// Subtitles bir videonun mevcut altyazı dillerini listeler.
func (s *AnalyzeService) Subtitles(raw string) (*SubtitleInfo, error) {
	p, err := s.ParseURL(raw)
	if err != nil {
		return nil, err
	}
	if p.VideoID == "" {
		return nil, errors.New("desteklenmeyen bağlantı: YouTube video URL'si gerekli")
	}
	target := "https://www.youtube.com/watch?v=" + p.VideoID
	ctx, endOperation, opErr := s.beginOperation(3 * time.Minute)
	if opErr != nil {
		return nil, opErr
	}
	defer endOperation()

	release, gateErr := acquireToolRead(ctx)
	if gateErr != nil {
		return nil, gateErr
	}
	var data []byte
	func() {
		defer release()
		data, err = engine.ExtractInfo(ctx, target, "--skip-download", "--no-playlist")
	}()
	if err != nil {
		return nil, err
	}
	var payload struct {
		Subtitles map[string][]struct {
			Ext  string `json:"ext"`
			Name string `json:"name"`
		} `json:"subtitles"`
		AutomaticCaptions map[string][]struct {
			Ext  string `json:"ext"`
			Name string `json:"name"`
		} `json:"automatic_captions"`
	}
	if err := json.Unmarshal(data, &payload); err != nil {
		return nil, fmt.Errorf("altyazı bilgisi çözümlenemedi: %w", err)
	}
	return &SubtitleInfo{
		Manual: tracks(payload.Subtitles, false),
		Auto:   tracks(payload.AutomaticCaptions, true),
	}, nil
}
