// ytdlp-studio:download-test v1
package services

import (
	"context"
	"testing"

	"ytdlp-studio/internal/model"
)

// newTestService worker başlatmayan bir DownloadService döndürür.
// Böylece testler yt-dlp/ffmpeg spawn etmez; sadece kuyruk ve state
// makineleri test edilir.
func newTestService() *DownloadService {
	return &DownloadService{
		queue:     make(chan downloadTask, 64),
		cancels:   map[string]context.CancelFunc{},
		canceled:  map[string]bool{},
		paused:    map[string]bool{},
		tasks:     map[string]downloadTask{},
		states:    map[string]string{},
		percents:  map[string]float64{},
		files:     map[string]string{},
		errors:    map[string]string{},
		batches:   map[string]*batchState{},
		taskBatch: map[string]string{},
	}
}

func testOptions(t *testing.T) model.DownloadOptions {
	t.Helper()
	o := model.DefaultOptions()
	o.OutputDir = t.TempDir()
	return o
}

func TestEnqueue_CreatesBatchAndTasks(t *testing.T) {
	d := newTestService()
	entries := []model.MediaEntry{
		{ID: "aaa", Title: "Video A", Available: true},
		{ID: "bbb", Title: "Video B", Available: true},
	}
	ids, err := d.Enqueue(entries, testOptions(t), BatchInfo{Title: "My Batch", Kind: "playlist"})
	if err != nil {
		t.Fatalf("Enqueue hata: %v", err)
	}
	if len(ids) != 2 {
		t.Fatalf("2 id bekleniyordu, %d geldi", len(ids))
	}
	if len(d.batches) != 1 {
		t.Fatalf("1 batch bekleniyordu, %d geldi", len(d.batches))
	}
	snap := d.Snapshot()
	if len(snap) != 2 {
		t.Fatalf("2 snapshot bekleniyordu, %d geldi", len(snap))
	}
	for _, p := range snap {
		if p.State != "queued" {
			t.Fatalf("state 'queued' bekleniyordu, %q geldi", p.State)
		}
	}
}

func TestEnqueue_EmptyEntries(t *testing.T) {
	d := newTestService()
	if _, err := d.Enqueue(nil, testOptions(t), BatchInfo{Title: "X"}); err == nil {
		t.Fatalf("boş entries için hata bekleniyordu")
	}
}

// Regression: Snapshot, TaskProgress.BatchTitle'da batch başlığını taşımalı
// (entry/task başlığını değil).
func TestSnapshot_BatchTitle(t *testing.T) {
	d := newTestService()
	entries := []model.MediaEntry{{ID: "x1", Title: "Entry Title", Available: true}}
	if _, err := d.Enqueue(entries, testOptions(t), BatchInfo{Title: "Batch Title", Kind: "playlist"}); err != nil {
		t.Fatalf("Enqueue hata: %v", err)
	}
	snap := d.Snapshot()
	if len(snap) != 1 {
		t.Fatalf("1 snapshot bekleniyordu, %d geldi", len(snap))
	}
	if snap[0].BatchTitle != "Batch Title" {
		t.Fatalf("BatchTitle 'Batch Title' olmalıydı, %q geldi", snap[0].BatchTitle)
	}
}

func TestCancel_UpdatesState(t *testing.T) {
	d := newTestService()
	ids, err := d.Enqueue(
		[]model.MediaEntry{{ID: "c1", Title: "C", Available: true}},
		testOptions(t), BatchInfo{Title: "B", Kind: "file"},
	)
	if err != nil {
		t.Fatalf("Enqueue: %v", err)
	}
	d.Cancel(ids[0])
	snap := d.Snapshot()
	if len(snap) != 1 || snap[0].State != "canceled" {
		t.Fatalf("canceled beklendi: %+v", snap)
	}
}

func TestPause_UpdatesState(t *testing.T) {
	d := newTestService()
	ids, err := d.Enqueue(
		[]model.MediaEntry{{ID: "p1", Title: "P", Available: true}},
		testOptions(t), BatchInfo{Title: "B", Kind: "file"},
	)
	if err != nil {
		t.Fatalf("Enqueue: %v", err)
	}
	d.Pause(ids[0])
	snap := d.Snapshot()
	if len(snap) != 1 || snap[0].State != "paused" {
		t.Fatalf("paused beklendi: %+v", snap)
	}
}

func TestClearFinished_RemovesDoneTasks(t *testing.T) {
	d := newTestService()
	ids, err := d.Enqueue(
		[]model.MediaEntry{
			{ID: "f1", Title: "F1", Available: true},
			{ID: "f2", Title: "F2", Available: true},
		},
		testOptions(t), BatchInfo{Title: "B", Kind: "playlist"},
	)
	if err != nil {
		t.Fatalf("Enqueue: %v", err)
	}
	d.Cancel(ids[0])
	d.ClearFinished()
	snap := d.Snapshot()
	if len(snap) != 1 {
		t.Fatalf("1 kalan görev bekleniyordu, %d geldi", len(snap))
	}
	if snap[0].TaskID != ids[1] {
		t.Fatalf("kalan görev %q olmalıydı, %q geldi", ids[1], snap[0].TaskID)
	}
}

func TestBatches_ReportsTotalAndProgress(t *testing.T) {
	d := newTestService()
	entries := []model.MediaEntry{
		{ID: "g1", Title: "G1", Available: true},
		{ID: "g2", Title: "G2", Available: true},
		{ID: "g3", Title: "G3", Available: true},
	}
	if _, err := d.Enqueue(entries, testOptions(t), BatchInfo{Title: "Three", Kind: "playlist"}); err != nil {
		t.Fatalf("Enqueue: %v", err)
	}
	bs := d.Batches()
	if len(bs) != 1 {
		t.Fatalf("1 batch bekleniyordu, %d geldi", len(bs))
	}
	if bs[0].Total != 3 {
		t.Fatalf("Total 3 olmalıydı, %d geldi", bs[0].Total)
	}
	if bs[0].Done {
		t.Fatalf("Done false olmalıydı (henüz hiçbir task tamamlanmadı)")
	}
}
