// ytdlp-studio:generated v1
//go:build !darwin

package main

import (
	"runtime"

	"github.com/wailsapp/wails/v3/pkg/application"
)

func tuneWindow(o *application.WebviewWindowOptions) {
	if runtime.GOOS == "windows" {
		o.Width, o.Height = 1366, 860
		o.MinWidth, o.MinHeight = 1024, 680
		return
	}
	o.Width, o.Height = 1280, 800
	o.MinWidth, o.MinHeight = 940, 600
}
