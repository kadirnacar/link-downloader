// ytdlp-studio:generated v1
// ytdlp-studio:main v4
package main

import (
	"embed"
	"log"

	"github.com/wailsapp/wails/v3/pkg/application"
	"ytdlp-studio/services"
)

//go:embed frontend/dist
var assets embed.FS

func main() {
	settings := services.NewSettingsService()
	appCfg := settings.LoadApp()

	deps := services.NewDepsService()
	download := services.NewDownloadService(appCfg.Workers)
	analyze := &services.AnalyzeService{}

	app := application.New(application.Options{
		Name: "ytdlp-studio",
		Services: []application.Service{
			application.NewService(analyze),
			application.NewService(download),
			application.NewService(settings),
			application.NewService(deps),
		},
		Assets: application.AssetOptions{
			Handler: application.AssetFileServerFS(assets),
		},
	})

	opts := application.WebviewWindowOptions{
		Title:     "ytdlp-studio",
		Width:     1280,
		Height:    840,
		MinWidth:  960,
		MinHeight: 620,
		URL:       "/",
	}
	tuneWindow(&opts)
	app.Window.NewWithOptions(opts)

	if appCfg.CheckDepsOnStart {
		go deps.CheckDeps()
	}
	if appCfg.YtDlpAutoUpdate {
		go func() { _, _ = deps.UpdateYtDlp(appCfg.YtDlpChannel) }()
	}

	if err := app.Run(); err != nil {
		log.Fatal(err)
	}
}
