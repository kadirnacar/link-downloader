// ytdlp-studio:generated v1
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
