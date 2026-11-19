// ytdlp-studio:generated v1
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
