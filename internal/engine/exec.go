// ytdlp-studio:generated v1
package engine

import (
	"bufio"
	"bytes"
	"context"
	"errors"
	"io"
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
	if err != nil {
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

// RunDownload yt-dlp'yi çalıştırır ve ilerlemeyi ayrıştırır.
func RunDownload(ctx context.Context, args []string, h Hooks) error {
	bin, err := binary()
	if err != nil {
		return err
	}
	cmd := exec.CommandContext(ctx, bin, args...)
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return err
	}
	stderr, err := cmd.StderrPipe()
	if err != nil {
		return err
	}
	if err := cmd.Start(); err != nil {
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

	scan := func(r io.Reader, isErr bool) {
		sc := bufio.NewScanner(r)
		sc.Buffer(make([]byte, 0, 64*1024), 1024*1024)
		for sc.Scan() {
			handle(sc.Text(), isErr)
		}
	}

	var wg sync.WaitGroup
	wg.Add(2)
	go func() { defer wg.Done(); scan(stdout, false) }()
	go func() { defer wg.Done(); scan(stderr, true) }()
	wg.Wait()

	werr := cmd.Wait()
	if ctx.Err() != nil {
		return ctx.Err()
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

// ExtractInfo tek JSON çıktısı döndürür.
func ExtractInfo(ctx context.Context, target string, extra ...string) ([]byte, error) {
	bin, err := binary()
	if err != nil {
		return nil, err
	}
	args := []string{"--ignore-config", "--no-colors", "--no-warnings", "--dump-single-json"}
	args = append(args, extra...)
	args = append(args, target)
	cmd := exec.CommandContext(ctx, bin, args...)
	var out, errb bytes.Buffer
	cmd.Stdout = &out
	cmd.Stderr = &errb
	if err := cmd.Run(); err != nil {
		msg := strings.TrimSpace(errb.String())
		if msg == "" {
			msg = err.Error()
		}
		return nil, errors.New(msg)
	}
	return out.Bytes(), nil
}

func Version(ctx context.Context) (string, error) {
	bin, err := binary()
	if err != nil {
		return "", err
	}
	out, err := exec.CommandContext(ctx, bin, "--version").Output()
	return strings.TrimSpace(string(out)), err
}
