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
		queue:          make(chan downloadTask, 64),
		runLocks:       map[string]*taskRunLock{},
		cancels:        map[string]context.CancelFunc{},
		cancelAttempts: map[string]uint64{},
		attempts:       map[string]uint64{},
		canceled:       map[string]bool{},
		paused:         map[string]bool{},
		tasks:          map[string]downloadTask{},
		states:         map[string]string{},
		percents:       map[string]float64{},
		files:          map[string]string{},
		errors:         map[string]string{},
		batches:        map[string]*batchState{},
		taskBatch:      map[string]string{},
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
		{ID: "aaaaaaaaaaa", Title: "Video A", Available: true},
		{ID: "bbbbbbbbbbb", Title: "Video B", Available: true},
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

func TestEnqueueRejectsUnsupportedHost(t *testing.T) {
	d := newTestService()
	_, err := d.Enqueue(
		[]model.MediaEntry{{ID: "dQw4w9WgXcQ", URL: "https://notyoutube.com/watch?v=dQw4w9WgXcQ", Title: "Lookalike", Available: true}},
		testOptions(t), BatchInfo{Title: "B", Kind: "file"},
	)
	if err == nil {
		t.Fatal("YouTube dışı URL kuyruğa alınmamalı")
	}
}

func TestEnqueueRejectsMismatchedEntryID(t *testing.T) {
	d := newTestService()
	_, err := d.Enqueue(
		[]model.MediaEntry{{
			ID: "aaaaaaaaaaa", URL: "https://www.youtube.com/watch?v=bbbbbbbbbbb",
			Title: "Mismatched", Available: true,
		}},
		testOptions(t), BatchInfo{Title: "B", Kind: "file"},
	)
	if err == nil {
		t.Fatal("MediaEntry ID ile URL video ID uyuşmuyorsa kuyruk kabul etmemeli")
	}
}

// Regression: Snapshot, TaskProgress.BatchTitle'da batch başlığını taşımalı
// (entry/task başlığını değil).
func TestSnapshot_BatchTitle(t *testing.T) {
	d := newTestService()
	entries := []model.MediaEntry{{ID: "xxxxxxxxxxx", Title: "Entry Title", Available: true}}
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
		[]model.MediaEntry{{ID: "ccccccccccc", Title: "C", Available: true}},
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
		[]model.MediaEntry{{ID: "ppppppppppp", Title: "P", Available: true}},
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

func TestCancelPausedTaskTransitionsToCanceled(t *testing.T) {
	d := newTestService()
	ids, err := d.Enqueue(
		[]model.MediaEntry{{ID: "ddddddddddd", Title: "Paused", Available: true}},
		testOptions(t), BatchInfo{Title: "B", Kind: "file"},
	)
	if err != nil {
		t.Fatalf("Enqueue: %v", err)
	}
	d.Pause(ids[0])
	d.Cancel(ids[0])
	snap := d.Snapshot()
	if len(snap) != 1 || snap[0].State != "canceled" {
		t.Fatalf("paused görev cancel sonrası canceled olmalı: %+v", snap)
	}
}

func TestClearFinished_RemovesDoneTasks(t *testing.T) {
	d := newTestService()
	ids, err := d.Enqueue(
		[]model.MediaEntry{
			{ID: "ffffffffff1", Title: "F1", Available: true},
			{ID: "ffffffffff2", Title: "F2", Available: true},
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

func TestResumeInvalidatesStaleQueuedAttempt(t *testing.T) {
	d := newTestService()
	ids, err := d.Enqueue(
		[]model.MediaEntry{{ID: "eeeeeeeeeee", Title: "Resume", Available: true}},
		testOptions(t), BatchInfo{Title: "B", Kind: "file"},
	)
	if err != nil {
		t.Fatalf("Enqueue: %v", err)
	}
	stale := <-d.queue
	d.Pause(ids[0])
	if err := d.Resume(ids[0]); err != nil {
		t.Fatalf("Resume: %v", err)
	}
	fresh := <-d.queue
	if stale.attempt == fresh.attempt {
		t.Fatalf("resume yeni attempt üretmeli: eski=%d yeni=%d", stale.attempt, fresh.attempt)
	}
	if _, ok := d.isRunnable(stale); ok {
		t.Fatal("eski kuyruk girdisi çalıştırılabilir olmamalı")
	}
	if _, ok := d.isRunnable(fresh); !ok {
		t.Fatal("güncel kuyruk girdisi çalıştırılabilir olmalı")
	}
}

func TestRemoveInvalidatesQueuedTask(t *testing.T) {
	d := newTestService()
	ids, err := d.Enqueue(
		[]model.MediaEntry{{ID: "rrrrrrrrrrr", Title: "Remove", Available: true}},
		testOptions(t), BatchInfo{Title: "B", Kind: "file"},
	)
	if err != nil {
		t.Fatalf("Enqueue: %v", err)
	}
	queued := <-d.queue
	d.Remove(ids[0])
	if _, ok := d.isRunnable(queued); ok {
		t.Fatal("silinen görev kuyruğa alınmış olsa bile çalıştırılmamalı")
	}
}

func TestFinishIsIdempotent(t *testing.T) {
	d := newTestService()
	ids, err := d.Enqueue(
		[]model.MediaEntry{{ID: "ggggggggggg", Title: "Finish", Available: true}},
		testOptions(t), BatchInfo{Title: "B", Kind: "file"},
	)
	if err != nil {
		t.Fatalf("Enqueue: %v", err)
	}
	d.mu.Lock()
	attempt := d.attempts[ids[0]]
	d.mu.Unlock()
	if !d.finish(ids[0], attempt, "error", "örnek hata", "") {
		t.Fatal("ilk finish çağrısı görevi tamamlamalı")
	}
	if d.finish(ids[0], attempt, "canceled", "", "") {
		t.Fatal("aynı attempt için ikinci terminal geçiş kabul edilmemeli")
	}
	snap := d.Snapshot()
	if len(snap) != 1 || snap[0].State != "error" {
		t.Fatalf("ilk terminal durum korunmalı: %+v", snap)
	}
}

func TestFinishDoesNotOverridePendingCancellation(t *testing.T) {
	d := newTestService()
	ids, err := d.Enqueue(
		[]model.MediaEntry{{ID: "kkkkkkkkkkk", Title: "Cancel Race", Available: true}},
		testOptions(t), BatchInfo{Title: "B", Kind: "file"},
	)
	if err != nil {
		t.Fatalf("Enqueue: %v", err)
	}
	d.mu.Lock()
	attempt := d.attempts[ids[0]]
	d.mu.Unlock()
	if !d.emitAttempt(TaskProgress{TaskID: ids[0], State: "downloading"}, attempt) {
		t.Fatal("görev downloading durumuna geçmeli")
	}

	// Simulate Cancel/Pause setting the intent before its terminal event is
	// committed. A worker's stale completion must not win this race.
	d.mu.Lock()
	d.canceled[ids[0]] = true
	d.mu.Unlock()
	if d.finish(ids[0], attempt, "done", "", "/tmp/video.mp4") {
		t.Fatal("iptal isteği beklerken görev done olmamalı")
	}
	if d.finish(ids[0], attempt, "error", "stale error", "") {
		t.Fatal("iptal isteği beklerken görev error olmamalı")
	}
	if !d.finish(ids[0], attempt, "canceled", "", "") {
		t.Fatal("iptal isteği canceled durumuna çevrilebilmeli")
	}
	snap := d.Snapshot()
	if len(snap) != 1 || snap[0].State != "canceled" {
		t.Fatalf("iptal sonucu korunmalı: %+v", snap)
	}
}

func TestBatches_ReportsTotalAndProgress(t *testing.T) {
	d := newTestService()
	entries := []model.MediaEntry{
		{ID: "hhhhhhhhhhh", Title: "G1", Available: true},
		{ID: "iiiiiiiiiii", Title: "G2", Available: true},
		{ID: "jjjjjjjjjjj", Title: "G3", Available: true},
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
