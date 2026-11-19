// ytdlp-studio:generated v1
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
