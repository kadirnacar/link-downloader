// ytdlp-studio:generated v1
// ytdlp-studio:settings v3
package services

import (
	"encoding/json"
	"os"
	"path/filepath"

	"ytdlp-studio/internal/engine"
	"ytdlp-studio/internal/model"
)

type SettingsService struct{}

func NewSettingsService() *SettingsService { return &SettingsService{} }

func configDir() (string, error) {
	base, err := os.UserConfigDir()
	if err != nil {
		return "", err
	}
	dir := filepath.Join(base, "ytdlp-studio")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return "", err
	}
	return dir, nil
}

func readJSON(name string, target any) bool {
	dir, err := configDir()
	if err != nil {
		return false
	}
	data, err := os.ReadFile(filepath.Join(dir, name))
	if err != nil {
		return false
	}
	return json.Unmarshal(data, target) == nil
}

func writeJSON(name string, v any) error {
	dir, err := configDir()
	if err != nil {
		return err
	}
	data, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(dir, name), data, 0o644)
}

func (s *SettingsService) Load() model.DownloadOptions {
	o := model.DefaultOptions()
	readJSON("settings.json", &o)
	return o
}

func (s *SettingsService) Save(o model.DownloadOptions) error {
	if err := model.Validate(o); err != nil {
		return err
	}
	return writeJSON("settings.json", o)
}

func (s *SettingsService) Reset() model.DownloadOptions {
	o := model.DefaultOptions()
	_ = writeJSON("settings.json", o)
	return o
}

func (s *SettingsService) LoadApp() model.AppSettings {
	a := model.DefaultAppSettings()
	readJSON("app.json", &a)
	return a
}

func (s *SettingsService) SaveApp(a model.AppSettings) error {
	if err := model.ValidateAppSettings(a); err != nil {
		return err
	}
	return writeJSON("app.json", a)
}

func (s *SettingsService) ResetApp() model.AppSettings {
	a := model.DefaultAppSettings()
	_ = writeJSON("app.json", a)
	return a
}

// PreviewArgs seçili ayarlarla üretilecek yt-dlp komutunu gösterir.
func (s *SettingsService) PreviewArgs(o model.DownloadOptions) []string {
	entry := model.MediaEntry{ID: "VIDEO_ID", Title: "Örnek Başlık", Index: 3}
	pl := engine.PlaylistContext{IsPlaylist: true, Title: "Örnek Playlist", ID: "PL123"}
	return engine.BuildArgs(o, entry, pl)
}

func (s *SettingsService) ConfigPath() string {
	dir, err := configDir()
	if err != nil {
		return ""
	}
	return dir
}
