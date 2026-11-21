// ytdlp-studio:generated v1
// ytdlp-studio:settings v3
package services

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"sync"

	"ytdlp-studio/internal/engine"
	"ytdlp-studio/internal/model"
)

type SettingsService struct {
	mu sync.Mutex
}

type settingsResetJournal struct {
	Version int                   `json:"version"`
	Options model.DownloadOptions `json:"options"`
	App     model.AppSettings     `json:"app"`
}

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
	if err := os.Rename(tmpName, filepath.Join(dir, name)); err != nil {
		return err
	}
	if runtime.GOOS != "windows" {
		if d, err := os.Open(dir); err == nil {
			_ = d.Sync()
			_ = d.Close()
		}
	}
	return nil
}

func (s *SettingsService) recoverResetLocked() error {
	dir, err := configDir()
	if err != nil {
		return err
	}
	journalPath := filepath.Join(dir, "settings-reset.json")
	data, err := os.ReadFile(journalPath)
	if errors.Is(err, os.ErrNotExist) {
		return nil
	}
	if err != nil {
		return err
	}
	var journal settingsResetJournal
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&journal); err != nil {
		return err
	}
	if err := decoder.Decode(&struct{}{}); err != io.EOF {
		return errors.New("ayar sıfırlama günlüğünde beklenmeyen ek veri var")
	}
	if journal.Version != 1 {
		return fmt.Errorf("desteklenmeyen ayar sıfırlama günlüğü: %d", journal.Version)
	}
	if err := model.Validate(journal.Options); err != nil {
		return err
	}
	if err := model.ValidateAppSettings(journal.App); err != nil {
		return err
	}
	if err := writeJSON("settings.json", journal.Options); err != nil {
		return err
	}
	if err := writeJSON("app.json", journal.App); err != nil {
		return err
	}
	if err := os.Remove(journalPath); err != nil && !errors.Is(err, os.ErrNotExist) {
		return err
	}
	if runtime.GOOS != "windows" {
		if d, e := os.Open(dir); e == nil {
			_ = d.Sync()
			_ = d.Close()
		}
	}
	return nil
}

func (s *SettingsService) resetAllLocked() (model.DownloadOptions, model.AppSettings, error) {
	options, app := model.DefaultOptions(), model.DefaultAppSettings()
	dir, err := configDir()
	if err != nil {
		return options, app, err
	}
	journal := settingsResetJournal{Version: 1, Options: options, App: app}
	data, err := json.MarshalIndent(journal, "", "  ")
	if err != nil {
		return options, app, err
	}
	journalPath := filepath.Join(dir, "settings-reset.json")
	tmp, err := os.CreateTemp(dir, ".settings-reset-*.tmp")
	if err != nil {
		return options, app, err
	}
	tmpName := tmp.Name()
	defer os.Remove(tmpName)
	if runtime.GOOS != "windows" {
		if err := tmp.Chmod(0o600); err != nil {
			_ = tmp.Close()
			return options, app, err
		}
	}
	if _, err := tmp.Write(data); err != nil {
		_ = tmp.Close()
		return options, app, err
	}
	if err := tmp.Sync(); err != nil {
		_ = tmp.Close()
		return options, app, err
	}
	if err := tmp.Close(); err != nil {
		return options, app, err
	}
	if err := os.Rename(tmpName, journalPath); err != nil {
		return options, app, err
	}
	if runtime.GOOS != "windows" {
		if d, e := os.Open(dir); e == nil {
			_ = d.Sync()
			_ = d.Close()
		}
	}
	if err := writeJSON("settings.json", options); err != nil {
		return options, app, err
	}
	if err := writeJSON("app.json", app); err != nil {
		return options, app, err
	}
	if err := os.Remove(journalPath); err != nil {
		return options, app, err
	}
	return options, app, nil
}

func (s *SettingsService) Load() model.DownloadOptions {
	s.mu.Lock()
	defer s.mu.Unlock()
	if err := s.recoverResetLocked(); err != nil {
		return model.DefaultOptions()
	}
	o := model.DefaultOptions()
	if !readJSON("settings.json", &o) || model.Validate(o) != nil {
		return model.DefaultOptions()
	}
	return o
}

func (s *SettingsService) Save(o model.DownloadOptions) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if err := s.recoverResetLocked(); err != nil {
		return err
	}
	if err := model.Validate(o); err != nil {
		return err
	}
	return writeJSON("settings.json", o)
}

func (s *SettingsService) Reset() (model.DownloadOptions, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	o, _, err := s.resetAllLocked()
	if err != nil {
		return model.DownloadOptions{}, err
	}
	return o, nil
}

func (s *SettingsService) LoadApp() model.AppSettings {
	s.mu.Lock()
	defer s.mu.Unlock()
	if err := s.recoverResetLocked(); err != nil {
		return model.DefaultAppSettings()
	}
	a := model.DefaultAppSettings()
	if !readJSON("app.json", &a) || model.ValidateAppSettings(a) != nil {
		return model.DefaultAppSettings()
	}
	return a
}

func (s *SettingsService) SaveApp(a model.AppSettings) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if err := s.recoverResetLocked(); err != nil {
		return err
	}
	if err := model.ValidateAppSettings(a); err != nil {
		return err
	}
	return writeJSON("app.json", a)
}

// ResetApp remains available for existing clients; resetting either settings
// surface commits both settings files through the same recoverable journal.
func (s *SettingsService) ResetApp() (model.AppSettings, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	_, app, err := s.resetAllLocked()
	if err != nil {
		return model.AppSettings{}, err
	}
	return app, nil
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
