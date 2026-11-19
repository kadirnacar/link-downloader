// ytdlp-studio:generated v1
package model

import "fmt"

// AppSettings uygulama davranışını ve görünümünü yönetir.
type AppSettings struct {
	Workers              int    `json:"workers"`
	Theme                string `json:"theme"`
	Accent               string `json:"accent"`
	Language             string `json:"language"`
	Notifications        bool   `json:"notifications"`
	ConfirmClearQueue    bool   `json:"confirmClearQueue"`
	ClipboardAutoAnalyze bool   `json:"clipboardAutoAnalyze"`
	CheckDepsOnStart     bool   `json:"checkDepsOnStart"`
	YtDlpAutoUpdate      bool   `json:"ytDlpAutoUpdate"`
	YtDlpChannel         string `json:"ytDlpChannel"`
	LogLevel             string `json:"logLevel"`
	MaxLogLines          int    `json:"maxLogLines"`
	DefaultTab           string `json:"defaultTab"`
	SidebarCollapsed     bool   `json:"sidebarCollapsed"`
}

func DefaultAppSettings() AppSettings {
	return AppSettings{
		Workers:           3,
		Theme:             "dark",
		Accent:            "blue",
		Language:          "tr",
		Notifications:     true,
		ConfirmClearQueue: true,
		CheckDepsOnStart:  true,
		YtDlpChannel:      "stable",
		LogLevel:          "info",
		MaxLogLines:       2000,
		DefaultTab:        "analyze",
	}
}

func ValidateAppSettings(a AppSettings) error {
	if a.Workers < 1 || a.Workers > 8 {
		return fmt.Errorf("workers 1-8 arası olmalı")
	}
	switch a.Theme {
	case "dark", "light":
	default:
		return fmt.Errorf("geçersiz tema: %q", a.Theme)
	}
	switch a.Accent {
	case "blue", "cyan", "green", "amber", "violet":
	default:
		return fmt.Errorf("geçersiz vurgu rengi: %q", a.Accent)
	}
	switch a.Language {
	case "tr", "en":
	default:
		return fmt.Errorf("geçersiz dil: %q", a.Language)
	}
	switch a.YtDlpChannel {
	case "stable", "nightly", "master":
	default:
		return fmt.Errorf("geçersiz yt-dlp kanalı: %q", a.YtDlpChannel)
	}
	switch a.LogLevel {
	case "info", "debug":
	default:
		return fmt.Errorf("geçersiz log seviyesi: %q", a.LogLevel)
	}
	switch a.DefaultTab {
	case "analyze", "queue", "settings", "logs", "about":
	default:
		return fmt.Errorf("geçersiz başlangıç sekmesi: %q", a.DefaultTab)
	}
	if a.MaxLogLines < 100 || a.MaxLogLines > 20000 {
		return fmt.Errorf("maxLogLines 100-20000 arası olmalı")
	}
	return nil
}
