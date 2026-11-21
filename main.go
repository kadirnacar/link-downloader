// ytdlp-studio:generated v1
// ytdlp-studio:main v4
package main

import (
	"context"
	"embed"
	"log"
	"time"

	"github.com/wailsapp/wails/v3/pkg/application"
	"ytdlp-studio/services"
)

//go:embed frontend/dist
var assets embed.FS

func main() {
	settings := services.NewSettingsService()
	appCfg := settings.LoadApp()

	appCtx, appCancel := context.WithCancel(context.Background())
	deps := services.NewDepsServiceWithContext(appCtx)
	download, err := services.NewPersistentDownloadService(appCfg.Workers)
	if err != nil {
		log.Fatalf("download queue could not be restored: %v", err)
	}
	analyze := services.NewAnalyzeService()

	app := application.New(application.Options{
		Name: "Link Downloader",
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
		Title: "Link Downloader",
		URL:   "/",
	}
	tuneWindow(&opts)
	app.Window.NewWithOptions(opts)
	app.OnShutdown(func() {
		appCancel()
		ctx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
		defer cancel()
		if err := services.ShutdownServices(ctx, analyze, download); err != nil {
			log.Printf("application service shutdown: %v", err)
		}
	})

	if appCfg.CheckDepsOnStart || appCfg.YtDlpAutoUpdate {
		go func() {
			if appCfg.CheckDepsOnStart {
				if _, err := deps.EnsureDeps(); err != nil {
					log.Printf("dependency check failed: %v", err)
				}
			} else {
				deps.CheckDeps()
			}
			if appCfg.YtDlpAutoUpdate {
				if _, err := deps.UpdateYtDlp(appCfg.YtDlpChannel); err != nil {
					log.Printf("yt-dlp auto-update failed (channel=%s): %v", appCfg.YtDlpChannel, err)
				}
			}
		}()
	}

	if err := app.Run(); err != nil {
		log.Fatal(err)
	}
}
