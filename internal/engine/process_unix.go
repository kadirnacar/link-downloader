//go:build aix || darwin || dragonfly || freebsd || linux || netbsd || openbsd || solaris

package engine

import (
	"os/exec"
	"syscall"
	"time"
)

func configureProcessTree(cmd *exec.Cmd) {
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
}

func terminateProcessTree(cmd *exec.Cmd) {
	if cmd == nil || cmd.Process == nil {
		return
	}
	pid := cmd.Process.Pid
	_ = syscall.Kill(-pid, syscall.SIGTERM)
	time.Sleep(900 * time.Millisecond)
	_ = syscall.Kill(-pid, syscall.SIGKILL)
}
