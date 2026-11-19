// ytdlp-studio:generated v1
package services

import (
	"encoding/json"
	"os"
	"path/filepath"

	"ytdlp-studio/internal/model"
)

type SettingsService struct{}

func NewSettingsService() *SettingsService { return &SettingsService{} }

func settingsPath() (string, error) {
	base, err := os.UserConfigDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(base, "ytdlp-studio", "settings.json"), nil
}

func (s *SettingsService) Load() model.DownloadOptions {
	o := model.DefaultOptions()
	p, err := settingsPath()
	if err != nil {
		return o
	}
	data, err := os.ReadFile(p)
	if err != nil {
		return o
	}
	_ = json.Unmarshal(data, &o)
	return o
}

func (s *SettingsService) Save(o model.DownloadOptions) error {
	if err := model.Validate(o); err != nil {
		return err
	}
	p, err := settingsPath()
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(o, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(p, data, 0o644)
}
