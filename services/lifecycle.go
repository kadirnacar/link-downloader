// ytdlp-studio:application-lifecycle v1
package services

import (
	"context"
	"errors"
	"sync"
)

// ShutdownServices is called by the Wails application hook. It is deliberately
// a package-level coordinator rather than a method on a bound service, so the
// generated frontend API remains limited to user-facing operations.
func ShutdownServices(ctx context.Context, analyze *AnalyzeService, download *DownloadService) error {
	var wg sync.WaitGroup
	var mu sync.Mutex
	var shutdownErrors []error
	add := func(err error) {
		if err == nil {
			return
		}
		mu.Lock()
		shutdownErrors = append(shutdownErrors, err)
		mu.Unlock()
	}
	if analyze != nil {
		wg.Add(1)
		go func() { defer wg.Done(); add(analyze.shutdown(ctx)) }()
	}
	if download != nil {
		wg.Add(1)
		go func() { defer wg.Done(); add(download.shutdown(ctx)) }()
	}
	done := make(chan struct{})
	go func() { wg.Wait(); close(done) }()
	select {
	case <-done:
		return errors.Join(shutdownErrors...)
	case <-ctx.Done():
		mu.Lock()
		collected := append([]error(nil), shutdownErrors...)
		mu.Unlock()
		return errors.Join(append(collected, ctx.Err())...)
	}
}
