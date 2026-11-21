// ytdlp-studio:managed-process v1
package engine

import (
	"context"
	"os/exec"
	"sync"
)

type managedProcess struct {
	cmd      *exec.Cmd
	done     chan struct{}
	mu       sync.Mutex
	finished bool
}

func startManagedProcess(ctx context.Context, cmd *exec.Cmd) (*managedProcess, error) {
	configureProcessTree(cmd)
	if err := cmd.Start(); err != nil {
		return nil, err
	}
	p := &managedProcess{cmd: cmd, done: make(chan struct{})}
	go func() {
		select {
		case <-ctx.Done():
			p.mu.Lock()
			if !p.finished {
				terminateProcessTree(p.cmd)
			}
			p.mu.Unlock()
		case <-p.done:
		}
	}()
	return p, nil
}

func (p *managedProcess) Wait() error {
	err := p.cmd.Wait()
	p.mu.Lock()
	p.finished = true
	close(p.done)
	p.mu.Unlock()
	return err
}
