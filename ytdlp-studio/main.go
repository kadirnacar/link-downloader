// ytdlp-studio:generated v1
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
	deps := services.NewDepsService()
	download := services.NewDownloadService(3)
	settings := services.NewSettingsService()
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

	app.NewWebviewWindowWithOptions(application.WebviewWindowOptions{
		Title:  "ytdlp-studio",
		Width:  1180,
		Height: 760,
		URL:    "/",
	})

	go deps.CheckDeps()

	if err := app.Run(); err != nil {
		log.Fatal(err)
	}
}
