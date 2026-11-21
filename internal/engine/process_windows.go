//go:build windows

package engine

import (
	"os/exec"
	"strconv"
)

func configureProcessTree(cmd *exec.Cmd) {}

func terminateProcessTree(cmd *exec.Cmd) {
	if cmd == nil || cmd.Process == nil {
		return
	}
	// taskkill /T terminates the yt-dlp process and its FFmpeg/runtime descendants.
	if err := exec.Command("taskkill.exe", "/PID", strconv.Itoa(cmd.Process.Pid), "/T", "/F").Run(); err != nil {
		_ = cmd.Process.Kill()
	}
}
