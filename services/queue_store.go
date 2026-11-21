// ytdlp-studio:queue-store v1
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

	"ytdlp-studio/internal/engine"
	"ytdlp-studio/internal/model"
)

const queueStoreVersion = 1
const maxQueueStoreBytes = 64 << 20

type persistedTask struct {
	ID         string                 `json:"id"`
	BatchID    string                 `json:"batchId"`
	BatchTitle string                 `json:"batchTitle"`
	Title      string                 `json:"title"`
	Attempt    uint64                 `json:"attempt"`
	Entry      model.MediaEntry       `json:"entry"`
	Options    model.DownloadOptions  `json:"options"`
	Playlist   engine.PlaylistContext `json:"playlist"`
	State      string                 `json:"state"`
	Percent    float64                `json:"percent"`
	FilePath   string                 `json:"filePath,omitempty"`
	Error      string                 `json:"error,omitempty"`
	QueueOrder uint64                 `json:"queueOrder"`
}

type persistedBatch struct {
	ID      string             `json:"id"`
	Title   string             `json:"title"`
	Kind    string             `json:"kind"`
	Total   int                `json:"total"`
	IDs     []string           `json:"ids"`
	Percent map[string]float64 `json:"percent"`
}

type queueSnapshot struct {
	Version       int              `json:"version"`
	Sequence      int              `json:"sequence"`
	BatchSequence int              `json:"batchSequence"`
	QueueSequence uint64           `json:"queueSequence"`
	Tasks         []persistedTask  `json:"tasks"`
	Batches       []persistedBatch `json:"batches"`
}

type queueStore struct{ path string }

func newQueueStore() (*queueStore, error) {
	dir, err := configDir()
	if err != nil {
		return nil, err
	}
	return &queueStore{path: filepath.Join(dir, "queue.json")}, nil
}

func (s *queueStore) Load() (queueSnapshot, error) {
	if s == nil {
		return queueSnapshot{}, errors.New("queue store not configured")
	}
	data, err := os.ReadFile(s.path)
	if errors.Is(err, os.ErrNotExist) {
		return queueSnapshot{Version: queueStoreVersion}, nil
	}
	if err != nil {
		return queueSnapshot{}, fmt.Errorf("kuyruk dosyası okunamadı: %w", err)
	}
	if len(data) > maxQueueStoreBytes {
		return queueSnapshot{}, errors.New("kuyruk dosyası izin verilen boyutu aşıyor")
	}
	var snapshot queueSnapshot
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&snapshot); err != nil {
		return queueSnapshot{}, fmt.Errorf("kuyruk dosyası çözümlenemedi: %w", err)
	}
	if err := dec.Decode(&struct{}{}); err != io.EOF {
		return queueSnapshot{}, errors.New("kuyruk dosyasında beklenmeyen ek veri var")
	}
	if snapshot.Version != queueStoreVersion {
		return queueSnapshot{}, fmt.Errorf("desteklenmeyen kuyruk sürümü: %d", snapshot.Version)
	}
	if len(snapshot.Tasks) > 100000 {
		return queueSnapshot{}, errors.New("kuyruk dosyasında çok fazla görev var")
	}
	return snapshot, nil
}

func (s *queueStore) Save(snapshot queueSnapshot) error {
	if s == nil {
		return nil
	}
	snapshot.Version = queueStoreVersion
	data, err := json.MarshalIndent(snapshot, "", "  ")
	if err != nil {
		return fmt.Errorf("kuyruk serileştirilemedi: %w", err)
	}
	dir := filepath.Dir(s.path)
	tmp, err := os.CreateTemp(dir, ".queue-*.tmp")
	if err != nil {
		return fmt.Errorf("geçici kuyruk dosyası oluşturulamadı: %w", err)
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
	if err := os.Rename(tmpName, s.path); err != nil {
		return fmt.Errorf("kuyruk dosyası değiştirilemedi: %w", err)
	}
	if runtime.GOOS != "windows" {
		if d, err := os.Open(dir); err == nil {
			_ = d.Sync()
			_ = d.Close()
		}
	}
	return nil
}
