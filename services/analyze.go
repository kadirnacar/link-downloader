// ytdlp-studio:generated v1
// ytdlp-studio:analyze v3
package services

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/url"
	"sort"
	"strings"
	"time"

	"ytdlp-studio/internal/engine"
	"ytdlp-studio/internal/model"
)

type AnalyzeService struct{}

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

	data, err := engine.ExtractInfo(ctx, target, engine.AnalyzeArgs(target, playlistItems, false)...)
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
	target := p.CanonicalURL
	if p.VideoID != "" {
		target = "https://www.youtube.com/watch?v=" + p.VideoID
	}
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Minute)
	defer cancel()

	data, err := engine.ExtractInfo(ctx, target, "--skip-download", "--no-playlist")
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
