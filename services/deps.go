// ytdlp-studio:generated v1
// ytdlp-studio:deps v3
package services

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"time"

	"github.com/lrstanley/go-ytdlp"
	"github.com/wailsapp/wails/v3/pkg/application"
	"ytdlp-studio/internal/engine"
)

type DepStatus struct {
	YtDlp     bool     `json:"ytDlp"`
	FFmpeg    bool     `json:"ffmpeg"`
	FFprobe   bool     `json:"ffprobe"`
	JSRuntime string   `json:"jsRuntime"`
	YtDlpPath string   `json:"ytDlpPath"`
	YtDlpVer  string   `json:"ytDlpVersion"`
	Missing   []string `json:"missing"`
}

type DepsService struct{}

func NewDepsService() *DepsService { return &DepsService{} }

func exeName(n string) string {
	if runtime.GOOS == "windows" {
		return n + ".exe"
	}
	return n
}

func look(name string) string {
	bin := exeName(name)
	if p, err := exec.LookPath(bin); err == nil {
		return p
	}
	dirs := []string{"/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"}
	if cache, err := ytdlp.GetCacheDir(); err == nil {
		dirs = append(dirs, cache)
	}
	if home, err := os.UserHomeDir(); err == nil {
		dirs = append(dirs, filepath.Join(home, ".local", "bin"))
	}
	for _, dir := range dirs {
		p := filepath.Join(dir, bin)
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
	st := DepStatus{
		YtDlp: yt != "", FFmpeg: ff != "", FFprobe: fp != "",
		JSRuntime: js, YtDlpPath: yt, Missing: []string{},
	}
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
	if yt != "" {
		ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
		if v, err := engine.Version(ctx); err == nil {
			st.YtDlpVer = v
		}
		cancel()
	}
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

// UpdateYtDlp seçili kanala göre günceller: stable | nightly | master.
func (s *DepsService) UpdateYtDlp(channel string) (string, error) {
	yt := look("yt-dlp")
	if yt == "" {
		return "", fmt.Errorf("yt-dlp bulunamadı; önce bileşenleri kurun")
	}
	args := []string{"-U"}
	switch channel {
	case "nightly":
		args = []string{"--update-to", "nightly"}
	case "master":
		args = []string{"--update-to", "master"}
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()
	out, err := exec.CommandContext(ctx, yt, args...).CombinedOutput()
	s.CheckDeps()
	return string(out), err
}

func (s *DepsService) YtDlpVersion() (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	return engine.Version(ctx)
}
