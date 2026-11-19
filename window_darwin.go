// ytdlp-studio:generated v1
//go:build darwin

package main

import "github.com/wailsapp/wails/v3/pkg/application"

func tuneWindow(o *application.WebviewWindowOptions) {
	o.Width, o.Height = 1280, 840
	o.MinWidth, o.MinHeight = 960, 620
}
