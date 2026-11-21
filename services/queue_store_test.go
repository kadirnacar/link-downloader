// ytdlp-studio:queue-store-test v1
package services

import (
	"os"
	"path/filepath"
	"reflect"
	"runtime"
	"testing"

	"ytdlp-studio/internal/engine"
	"ytdlp-studio/internal/model"
)

func TestQueueStoreRoundTrip(t *testing.T) {
	store := &queueStore{path: filepath.Join(t.TempDir(), "queue.json")}
	want := queueSnapshot{
		Version:       queueStoreVersion,
		Sequence:      42,
		BatchSequence: 3,
		QueueSequence: 9,
		Tasks: []persistedTask{{
			ID: "dQw4w9WgXcQ-42", BatchID: "batch-3", BatchTitle: "Playlist",
			Title: "Example", Attempt: 2,
			Entry:    model.MediaEntry{ID: "dQw4w9WgXcQ", URL: "https://www.youtube.com/watch?v=dQw4w9WgXcQ", Available: true},
			Options:  model.DefaultOptions(),
			Playlist: engine.PlaylistContext{IsPlaylist: true, Title: "Playlist", ID: "PLexample"},
			State:    "paused", Percent: 37.5, FilePath: "/tmp/example.part", Error: "interrupted", QueueOrder: 9,
		}},
		Batches: []persistedBatch{{
			ID: "batch-3", Title: "Playlist", Kind: "playlist", Total: 1,
			IDs: []string{"dQw4w9WgXcQ-42"}, Percent: map[string]float64{"dQw4w9WgXcQ-42": 37.5},
		}},
	}

	if err := store.Save(want); err != nil {
		t.Fatalf("Save() error = %v", err)
	}
	got, err := store.Load()
	if err != nil {
		t.Fatalf("Load() error = %v", err)
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("queue round-trip mismatch:\n got: %#v\nwant: %#v", got, want)
	}

	if runtime.GOOS != "windows" {
		info, err := os.Stat(store.path)
		if err != nil {
			t.Fatalf("stat queue file: %v", err)
		}
		if info.Mode().Perm() != 0o600 {
			t.Fatalf("queue file permissions = %04o, want 0600", info.Mode().Perm())
		}
	}
}

func TestQueueStoreRejectsInvalidDocuments(t *testing.T) {
	cases := []struct {
		name string
		json string
	}{
		{name: "unsupported version", json: `{"version":99}`},
		{name: "unknown field", json: `{"version":1,"unexpected":true}`},
		{name: "trailing document", json: `{"version":1} {"version":1}`},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			store := &queueStore{path: filepath.Join(t.TempDir(), "queue.json")}
			if err := os.WriteFile(store.path, []byte(tc.json), 0o600); err != nil {
				t.Fatalf("write invalid queue: %v", err)
			}
			if _, err := store.Load(); err == nil {
				t.Fatal("Load() accepted an invalid queue document")
			}
		})
	}
}
