// ytdlp-studio:generated v1
// ytdlp-studio:settings v3
package services

import (
	"bytes"
	"encoding/json"
	"io"
	"os"
	"path/filepath"
	"runtime"

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
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return "", err
	}
	if runtime.GOOS != "windows" {
		if err := os.Chmod(dir, 0o700); err != nil {
			return "", err
		}
	}
	return dir, nil
}

func readJSON[T any](name string, target *T) bool {
	dir, err := configDir()
	if err != nil {
		return false
	}
	data, err := os.ReadFile(filepath.Join(dir, name))
	if err != nil {
		return false
	}
	decoded := *target
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&decoded); err != nil {
		return false
	}
	if err := decoder.Decode(&struct{}{}); err != io.EOF {
		return false
	}
	*target = decoded
	return true
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
	tmp, err := os.CreateTemp(dir, "."+name+"-*.tmp")
	if err != nil {
		return err
	}
	tmpName := tmp.Name()
	defer os.Remove(tmpName)
	if runtime.GOOS != "windows" {
		if err := tmp.Chmod(0o600); err != nil {
			_ = tmp.Close()
			return err
		}
	}
	if _, err := tmp.Write(data); err != nil {
		_ = tmp.Close()
		return err
	}
	if err := tmp.Sync(); err != nil {
		_ = tmp.Close()
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	return os.Rename(tmpName, filepath.Join(dir, name))
}

func (s *SettingsService) Load() model.DownloadOptions {
	o := model.DefaultOptions()
	if !readJSON("settings.json", &o) || model.Validate(o) != nil {
		return model.DefaultOptions()
	}
	return o
}

func (s *SettingsService) Save(o model.DownloadOptions) error {
	if err := model.Validate(o); err != nil {
		return err
	}
	return writeJSON("settings.json", o)
}

func (s *SettingsService) Reset() (model.DownloadOptions, error) {
	o := model.DefaultOptions()
	if err := writeJSON("settings.json", o); err != nil {
		return model.DownloadOptions{}, err
	}
	return o, nil
}

func (s *SettingsService) LoadApp() model.AppSettings {
	a := model.DefaultAppSettings()
	if !readJSON("app.json", &a) || model.ValidateAppSettings(a) != nil {
		return model.DefaultAppSettings()
	}
	return a
}

func (s *SettingsService) SaveApp(a model.AppSettings) error {
	if err := model.ValidateAppSettings(a); err != nil {
		return err
	}
	return writeJSON("app.json", a)
}

func (s *SettingsService) ResetApp() (model.AppSettings, error) {
	a := model.DefaultAppSettings()
	if err := writeJSON("app.json", a); err != nil {
		return model.AppSettings{}, err
	}
	return a, nil
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
