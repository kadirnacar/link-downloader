// ytdlp-studio:generated v1
// ytdlp-studio:deps v5
package services

import (
	"context"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"time"

	"github.com/lrstanley/go-ytdlp"
	"github.com/wailsapp/wails/v3/pkg/application"
	"ytdlp-studio/internal/engine"
)

type DepStatus struct {
	YtDlp       bool     `json:"ytDlp"`
	FFmpeg      bool     `json:"ffmpeg"`
	FFprobe     bool     `json:"ffprobe"`
	JSRuntime   string   `json:"jsRuntime"`
	YtDlpPath   string   `json:"ytDlpPath"`
	YtDlpVer    string   `json:"ytDlpVersion"`
	FFmpegPath  string   `json:"ffmpegPath"`
	FFprobePath string   `json:"ffprobePath"`
	ToolDir     string   `json:"toolDir"`
	Missing     []string `json:"missing"`
	Notes       []string `json:"notes"`
}

type DepsService struct {
	mu sync.Mutex
}

func NewDepsService() *DepsService { return &DepsService{} }

func exeName(n string) string {
	if runtime.GOOS == "windows" {
		return n + ".exe"
	}
	return n
}

func depsToolDir() string {
	base, err := os.UserConfigDir()
	if err != nil {
		return ""
	}
	dir := filepath.Join(base, "ytdlp-studio", "bin")
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return ""
	}
	if runtime.GOOS != "windows" {
		if err := os.Chmod(dir, 0o700); err != nil {
			return ""
		}
	}
	return dir
}

// candidateDirs işletim sistemine göre gerçek binary dizinlerini döndürür.
func candidateDirs() []string {
	var dirs []string
	home, _ := os.UserHomeDir()
	if cache, err := ytdlp.GetCacheDir(); err == nil {
		dirs = append(dirs, cache)
	}
	if td := depsToolDir(); td != "" {
		dirs = append(dirs, td)
	}
	switch runtime.GOOS {
	case "windows":
		dirs = append(dirs,
			`C:\ffmpeg\bin`,
			`C:\Program Files\ffmpeg\bin`,
			`C:\ProgramData\chocolatey\bin`,
		)
		if la := os.Getenv("LOCALAPPDATA"); la != "" {
			dirs = append(dirs,
				filepath.Join(la, "Microsoft", "WinGet", "Links"),
				filepath.Join(la, "Programs", "Python", "Scripts"),
			)
		}
		if home != "" {
			dirs = append(dirs, filepath.Join(home, "scoop", "shims"), filepath.Join(home, ".bun", "bin"))
		}
	case "darwin":
		dirs = append(dirs, "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin", "/opt/local/bin")
		if home != "" {
			dirs = append(dirs, filepath.Join(home, ".local", "bin"), filepath.Join(home, ".bun", "bin"))
		}
	default:
		dirs = append(dirs, "/usr/bin", "/usr/local/bin", "/bin", "/snap/bin", "/var/lib/flatpak/exports/bin")
		if home != "" {
			dirs = append(dirs,
				filepath.Join(home, ".local", "bin"),
				filepath.Join(home, "bin"),
				filepath.Join(home, ".bun", "bin"),
				filepath.Join(home, ".deno", "bin"),
			)
		}
	}
	return dirs
}

func isShim(p string) bool {
	sep := string(filepath.Separator)
	return strings.Contains(p, sep+"shims"+sep) || strings.Contains(p, sep+"pyenv"+sep)
}

// look gerçek binary'yi bulur; shim dizinlerini en sona atar.
func look(name string) string {
	bin := exeName(name)
	var preferred, fallback []string
	for _, dir := range candidateDirs() {
		p := filepath.Join(dir, bin)
		if st, err := os.Stat(p); err == nil && !st.IsDir() {
			if isShim(p) {
				fallback = append(fallback, p)
			} else {
				preferred = append(preferred, p)
			}
		}
	}
	if p, err := exec.LookPath(bin); err == nil {
		if isShim(p) {
			fallback = append(fallback, p)
		} else {
			preferred = append(preferred, p)
		}
	}
	if len(preferred) > 0 {
		return preferred[0]
	}
	if len(fallback) > 0 {
		return fallback[0]
	}
	return ""
}

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	out, err := os.OpenFile(dst, os.O_CREATE|os.O_TRUNC|os.O_WRONLY, 0o755)
	if err != nil {
		return err
	}
	defer out.Close()
	_, err = io.Copy(out, in)
	return err
}

func linkOrCopy(src, dst string) error {
	if src == "" {
		return fmt.Errorf("kaynak yok")
	}
	if filepath.Clean(src) == filepath.Clean(dst) {
		return nil
	}
	_ = os.Remove(dst)
	if runtime.GOOS != "windows" {
		if err := os.Symlink(src, dst); err == nil {
			return nil
		}
	}
	return copyFile(src, dst)
}

// prepareToolDir ffmpeg ve ffprobe'u aynı dizinde toplar; yt-dlp ikisini birlikte bulur.
func prepareToolDir(ff, fp string) string {
	if ff == "" || fp == "" {
		return ""
	}
	dir := depsToolDir()
	if dir == "" {
		return ""
	}
	if err := linkOrCopy(ff, filepath.Join(dir, exeName("ffmpeg"))); err != nil {
		return ""
	}
	if err := linkOrCopy(fp, filepath.Join(dir, exeName("ffprobe"))); err != nil {
		return ""
	}
	return dir
}

func probeVersion(bin string, arg string, timeout time.Duration) (string, error) {
	if bin == "" {
		return "", fmt.Errorf("binary yok")
	}
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	out, err := exec.CommandContext(ctx, bin, arg).Output()
	if err != nil {
		return "", err
	}
	line := strings.TrimSpace(string(out))
	if i := strings.IndexAny(line, "\r\n"); i > 0 {
		line = line[:i]
	}
	return strings.TrimSpace(line), nil
}

func manualHint(component string) string {
	switch runtime.GOOS {
	case "darwin":
		return "Elle kurulum: brew install " + component
	case "windows":
		if component == "ffmpeg" || component == "ffprobe" {
			return "Elle kurulum: winget install Gyan.FFmpeg"
		}
		return "Elle kurulum: winget install yt-dlp.yt-dlp"
	default:
		return "Elle kurulum: sudo apt install " + component + " (veya dağıtımınızın paket yöneticisi)"
	}
}

func (s *DepsService) CheckDeps() DepStatus {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.checkDeps()
}

func (s *DepsService) checkDeps() DepStatus {
	yt, ff, fp := look("yt-dlp"), look("ffmpeg"), look("ffprobe")
	js := ""
	if look("deno") != "" {
		js = "deno"
	} else if look("bun") != "" {
		js = "bun"
	}

	td := prepareToolDir(ff, fp)
	ffLoc := td
	if ffLoc == "" {
		ffLoc = ff
	}
	engine.SetPaths(yt, ffLoc)

	st := DepStatus{
		YtDlp: yt != "", FFmpeg: ff != "", FFprobe: fp != "", JSRuntime: js,
		YtDlpPath: yt, FFmpegPath: ff, FFprobePath: fp, ToolDir: td,
		Missing: []string{}, Notes: []string{},
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
	if yt != "" {
		if v, err := probeVersion(yt, "--version", 25*time.Second); err == nil {
			st.YtDlpVer = v
		} else {
			st.Notes = append(st.Notes, "yt-dlp çalıştırılamadı: "+err.Error())
		}
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
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.installDeps()
}

func (s *DepsService) installDeps() (DepStatus, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 25*time.Minute)
	defer cancel()
	st := s.checkDeps()

	if !st.YtDlp {
		if err := safeInstall(func() { ytdlp.MustInstall(ctx, nil) }); err != nil {
			st.Notes = append(st.Notes, "yt-dlp otomatik kurulum başarısız: "+err.Error()+" · "+manualHint("yt-dlp"))
		}
	}
	if !st.FFmpeg {
		if err := safeInstall(func() { ytdlp.MustInstallFFmpeg(ctx, nil) }); err != nil {
			st.Notes = append(st.Notes, "ffmpeg otomatik kurulum başarısız: "+err.Error()+" · "+manualHint("ffmpeg"))
		}
	}
	if !st.FFprobe {
		if err := safeInstall(func() { ytdlp.MustInstallFFprobe(ctx, nil) }); err != nil {
			st.Notes = append(st.Notes, "ffprobe otomatik kurulum başarısız: "+err.Error()+" · "+manualHint("ffmpeg"))
		}
	}
	if st.JSRuntime == "" {
		if err := safeInstall(func() { ytdlp.MustInstallBun(ctx, nil) }); err != nil {
			st.Notes = append(st.Notes, "bun otomatik kurulum başarısız: "+err.Error()+" (JS runtime opsiyoneldir)")
		}
	}

	after := s.checkDeps()
	after.Notes = append(after.Notes, st.Notes...)
	hard := []string{}
	for _, m := range after.Missing {
		if m != "deno/bun" {
			hard = append(hard, m)
		}
	}
	if len(hard) > 0 {
		return after, fmt.Errorf("kurulamadı: %s", strings.Join(hard, ", "))
	}
	return after, nil
}

// EnsureDeps eksikleri indirir, kurar ve binary'leri gerçekten çalıştırarak doğrular.
func (s *DepsService) EnsureDeps() (DepStatus, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	st := s.checkDeps()
	var err error
	var verificationErrors []string
	if len(st.Missing) > 0 {
		st, err = s.installDeps()
	}
	if st.YtDlpPath != "" && st.YtDlpVer == "" {
		verificationErrors = append(verificationErrors, "yt-dlp")
	}
	if st.FFmpegPath != "" {
		if v, e := probeVersion(st.FFmpegPath, "-version", 25*time.Second); e != nil {
			st.Notes = append(st.Notes, "ffmpeg doğrulanamadı: "+e.Error())
			verificationErrors = append(verificationErrors, "ffmpeg")
		} else {
			st.Notes = append(st.Notes, "ffmpeg OK · "+v)
		}
	}
	if st.FFprobePath != "" {
		if v, e := probeVersion(st.FFprobePath, "-version", 25*time.Second); e != nil {
			st.Notes = append(st.Notes, "ffprobe doğrulanamadı: "+e.Error())
			verificationErrors = append(verificationErrors, "ffprobe")
		} else {
			st.Notes = append(st.Notes, "ffprobe OK · "+v)
		}
	}
	if st.ToolDir != "" {
		st.Notes = append(st.Notes, "ffmpeg+ffprobe birlikte: "+st.ToolDir)
	}
	if app := application.Get(); app != nil {
		app.Event.Emit("deps:status", st)
	}
	if err == nil && len(verificationErrors) > 0 {
		err = fmt.Errorf("bileşen doğrulaması başarısız: %s", strings.Join(verificationErrors, ", "))
	}
	return st, err
}

func (s *DepsService) UpdateYtDlp(channel string) (string, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
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
	s.checkDeps()
	return string(out), err
}
