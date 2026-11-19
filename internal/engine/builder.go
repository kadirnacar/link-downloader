// ytdlp-studio:generated v1
// ytdlp-studio:output-template v2
package engine

import (
	"fmt"
	"strings"
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

// ResolveNameTemplate, playlist_index ve playlist türevi alanları uygulama tarafında
// gerçek değerlerle doldurur. Böylece yt-dlp'nin "NA"/"000" fallback'i devreye girmez.
func ResolveNameTemplate(tmpl string, entry model.MediaEntry) string {
	out := tmpl
	if entry.Index > 0 {
		out = strings.ReplaceAll(out, "%(playlist_index)03d", fmt.Sprintf("%03d", entry.Index))
		out = strings.ReplaceAll(out, "%(playlist_index)s", fmt.Sprintf("%d", entry.Index))
		out = strings.ReplaceAll(out, "%(playlist_index)d", fmt.Sprintf("%d", entry.Index))
	} else {
		// Tekil indirmelerde playlist_index yoksa parçayı temizle
		out = strings.ReplaceAll(out, "%(playlist_index)03d - ", "")
		out = strings.ReplaceAll(out, "%(playlist_index)s - ", "")
		out = strings.ReplaceAll(out, "%(playlist_index)d - ", "")
		out = strings.ReplaceAll(out, "%(playlist_index)03d", "")
		out = strings.ReplaceAll(out, "%(playlist_index)s", "")
		out = strings.ReplaceAll(out, "%(playlist_index)d", "")
	}
	return out
}

// BuildCommand, her giriş için ayrı adlandırılmış komut üretir.
func BuildCommand(o model.DownloadOptions, entry model.MediaEntry) *ytdlp.Command {
	c := NewCommand().
		NoPlaylist().
		Paths("home:" + o.OutputDir).
		Output(ResolveNameTemplate(o.NameTemplate, entry))

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
