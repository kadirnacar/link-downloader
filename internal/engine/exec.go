// ytdlp-studio:generated v1
// ytdlp-studio:exec v4
package engine

import (
	"bufio"
	"bytes"
	"context"
	"errors"
	"fmt"
	"io"
	"math"
	"os/exec"
	"strconv"
	"strings"
	"sync"
)

type Progress struct {
	Downloaded float64
	Total      float64
	Speed      float64
	ETA        float64
	Filename   string
}

type Hooks struct {
	OnProgress    func(Progress)
	OnPostprocess func(string)
	OnFile        func(string)
	OnLog         func(string)
}

func num(s string) float64 {
	s = strings.TrimSpace(s)
	if s == "" || s == "NA" || s == "None" {
		return 0
	}
	v, err := strconv.ParseFloat(s, 64)
	if err != nil || math.IsNaN(v) || math.IsInf(v, 0) {
		return 0
	}
	return v
}

func binary() (string, error) {
	b := YtDlpPath()
	if b == "" {
		return "", errors.New("yt-dlp bulunamadı; Ayarlar > Bileşenler ekranından kurun")
	}
	return b, nil
}

// RunDownload argümanların SONUNA '-- <url>' ekleyerek çalıştırır.
var sensitiveArgumentFlags = map[string]bool{
	"--cookies":              true,
	"--cookies-from-browser": true,
	"--proxy":                true,
	"--username":             true,
	"-u":                     true,
	"--password":             true,
	"-p":                     true,
	"--video-password":       true,
	"--ap-password":          true,
	"--add-headers":          true,
	"--add-header":           true,
	"--extractor-args":       true,
	"--exec":                 true,
	"--exec-before-download": true,
	"--postprocessor-args":   true,
	"--referer":              true,
	"--paths":                true,
	"-P":                     true,
	"-o":                     true,
	"--output":               true,
	"--download-archive":     true,
	"--cache-dir":            true,
	"--ffmpeg-location":      true,
	"--config-locations":     true,
}

// redactArgsForLog removes credentials and private local paths from command logs.
func redactArgsForLog(args []string) []string {
	redacted := make([]string, len(args))
	hideNext := false
	for i, arg := range args {
		if hideNext {
			redacted[i] = "[REDACTED]"
			hideNext = false
			continue
		}
		flag, _, hasValue := strings.Cut(arg, "=")
		if !sensitiveArgumentFlags[flag] {
			redacted[i] = arg
			continue
		}
		if hasValue {
			redacted[i] = flag + "=[REDACTED]"
		} else {
			redacted[i] = arg
			hideNext = true
		}
	}
	return redacted
}

func RunDownload(ctx context.Context, args []string, url string, h Hooks) error {
	bin, err := binary()
	if err != nil {
		return err
	}
	target := strings.TrimSpace(url)
	if target == "" {
		return errors.New("indirme URL'si boş; öğe çözümlenemedi")
	}

	final := make([]string, 0, len(args)+2)
	for _, a := range args {
		if a == "--" {
			continue
		}
		final = append(final, a)
	}
	final = append(final, "--", target)

	if h.OnLog != nil {
		h.OnLog("cmd: yt-dlp " + strings.Join(redactArgsForLog(final), " "))
	}

	cmd := exec.Command(bin, final...)
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return err
	}
	stderr, err := cmd.StderrPipe()
	if err != nil {
		return err
	}
	process, err := startManagedProcess(ctx, cmd)
	if err != nil {
		return err
	}

	var emu sync.Mutex
	var tail []string

	handle := func(line string, isErr bool) {
		switch {
		case strings.HasPrefix(line, "PROG|"):
			p := strings.SplitN(strings.TrimPrefix(line, "PROG|"), "|", 6)
			if len(p) >= 6 && h.OnProgress != nil {
				total := num(p[1])
				if total == 0 {
					total = num(p[2])
				}
				h.OnProgress(Progress{
					Downloaded: num(p[0]), Total: total,
					Speed: num(p[3]), ETA: num(p[4]), Filename: p[5],
				})
			}
		case strings.HasPrefix(line, "PP|"):
			p := strings.SplitN(strings.TrimPrefix(line, "PP|"), "|", 2)
			if len(p) >= 2 && h.OnPostprocess != nil {
				h.OnPostprocess(p[1])
			}
		case strings.HasPrefix(line, "FILE|"):
			if h.OnFile != nil {
				h.OnFile(strings.TrimSpace(strings.TrimPrefix(line, "FILE|")))
			}
		default:
			if strings.TrimSpace(line) == "" {
				return
			}
			if h.OnLog != nil {
				h.OnLog(line)
			}
			if isErr {
				emu.Lock()
				tail = append(tail, line)
				if len(tail) > 12 {
					tail = tail[len(tail)-12:]
				}
				emu.Unlock()
			}
		}
	}

	scan := func(r io.Reader, isErr bool) error {
		sc := bufio.NewScanner(r)
		sc.Buffer(make([]byte, 0, 64*1024), 1024*1024)
		for sc.Scan() {
			handle(sc.Text(), isErr)
		}
		return sc.Err()
	}

	scanErrs := make(chan error, 2)
	var wg sync.WaitGroup
	readPipe := func(r io.Reader, isErr bool) {
		defer wg.Done()
		if err := scan(r, isErr); err != nil {
			scanErrs <- err
			// Scanner bir token sınırına takılırsa pipe'ı tüketmeye devam et.
			// Aksi hâlde yt-dlp pipe buffer'ı dolduğu için çıkışta kilitlenebilir.
			_, _ = io.Copy(io.Discard, r)
		}
	}

	wg.Add(2)
	go readPipe(stdout, false)
	go readPipe(stderr, true)
	wg.Wait()
	close(scanErrs)

	werr := process.Wait()
	var scanErr error
	for err := range scanErrs {
		if scanErr == nil {
			scanErr = err
		}
	}
	if ctx.Err() != nil {
		return ctx.Err()
	}
	if scanErr != nil {
		if werr != nil {
			return fmt.Errorf("yt-dlp çıktısı okunamadı: %v (komut hatası: %w)", scanErr, werr)
		}
		return fmt.Errorf("yt-dlp çıktısı okunamadı: %w", scanErr)
	}
	if werr != nil {
		emu.Lock()
		msg := strings.Join(tail, "\n")
		emu.Unlock()
		if msg == "" {
			msg = werr.Error()
		}
		return errors.New(msg)
	}
	return nil
}

func ExtractInfo(ctx context.Context, target string, extra ...string) ([]byte, error) {
	bin, err := binary()
	if err != nil {
		return nil, err
	}
	if strings.TrimSpace(target) == "" {
		return nil, errors.New("analiz URL'si boş")
	}
	args := []string{"--ignore-config", "--no-colors", "--no-warnings", "--dump-single-json"}
	for _, a := range extra {
		if a != "--" {
			args = append(args, a)
		}
	}
	args = append(args, "--", target)

	cmd := exec.Command(bin, args...)
	var out, errb bytes.Buffer
	cmd.Stdout = &out
	cmd.Stderr = &errb
	process, startErr := startManagedProcess(ctx, cmd)
	if startErr != nil {
		return nil, startErr
	}
	if err := process.Wait(); err != nil {
		msg := strings.TrimSpace(errb.String())
		if msg == "" {
			msg = err.Error()
		}
		return nil, errors.New(msg)
	}
	return out.Bytes(), nil
}
