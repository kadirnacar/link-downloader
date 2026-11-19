// ytdlp-studio:generated v1
// ytdlp-studio:output-template v1
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

// BuildCommand builds a yt-dlp command with the given options and entry.
// It replaces %(playlist_index)s with the entry's Index value to avoid "000" fallback.
func BuildCommand(o model.DownloadOptions, entry model.MediaEntry) *ytdlp.Command {
	// Replace %(playlist_index)s with actual index value
	template := o.NameTemplate
	if entry.Index > 0 {
		template = strings.ReplaceAll(template, "%(playlist_index)s", fmt.Sprintf("%d", entry.Index))
		template = strings.ReplaceAll(template, "%(playlist_index)03d", fmt.Sprintf("%03d", entry.Index))
	} else {
		// Fallback: remove playlist_index if index is 0
		template = strings.ReplaceAll(template, "%(playlist_index)s - ", "")
		template = strings.ReplaceAll(template, "%(playlist_index)03d - ", "")
	}

	c := NewCommand().
		NoPlaylist().
		Paths("home:" + o.OutputDir).
		Output(template)

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
