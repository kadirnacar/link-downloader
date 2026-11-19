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

// ytdlp-studio:playlist-all-analyze v2
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

// ytdlp-studio:playlist-all-thumb v2
func thumbOf(e *ytdlp.ExtractedInfo) string {
	return plAllThumbnail(e)
}
