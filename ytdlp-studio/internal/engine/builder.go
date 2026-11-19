// ytdlp-studio:generated v1
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
