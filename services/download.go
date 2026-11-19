// ytdlp-studio:generated v1
// ytdlp-studio:download-progress v1
package services

import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"time"

	"github.com/lrstanley/go-ytdlp"
	"github.com/wailsapp/wails/v3/pkg/application"
	"ytdlp-studio/internal/engine"
	"ytdlp-studio/internal/model"
)

type TaskProgress struct {
	TaskID   string  `json:"taskId"`
	State    string  `json:"state"`
	Percent  float64 `json:"percent"`
	Speed    float64 `json:"speedBps"`
	ETA      float64 `json:"etaSec"`
	Error    string  `json:"error,omitempty"`
	FilePath string  `json:"filePath,omitempty"`
	BatchID  string  `json:"batchId,omitempty"`
}

type BatchProgress struct {
	BatchID   string `json:"batchId"`
	Total     int    `json:"total"`
	Completed int    `json:"completed"`
	Current   int    `json:"current"`
	Failed    int    `json:"failed"`
}

type downloadTask struct {
	id      string
	batchID string
	entry   model.MediaEntry
	opts    model.DownloadOptions
}

type DownloadService struct {
	mu       sync.Mutex
	queue    chan downloadTask
	cancels  map[string]context.CancelFunc
	canceled map[string]bool
	tasks    map[string]downloadTask
	batches  map[string]*batchState
	seq      int
}

type batchState struct {
	total     int
	completed int
	current   int
	failed    int
	mu        sync.Mutex
}

func NewDownloadService(workers int) *DownloadService {
	if workers < 1 {
		workers = 1
	}
	d := &DownloadService{
		queue:    make(chan downloadTask, 4096),
		cancels:  map[string]context.CancelFunc{},
		canceled: map[string]bool{},
		tasks:    map[string]downloadTask{},
		batches:  map[string]*batchState{},
	}
	for i := 0; i < workers; i++ {
		go d.worker()
	}
	return d
}

func (d *DownloadService) PickFolder() (string, error) {
	return application.Get().Dialog.OpenFile().
		SetTitle("İndirme Klasörü Seç").
		CanChooseDirectories(true).
		CanChooseFiles(false).
		PromptForSingleSelection()
}

func (d *DownloadService) Enqueue(entries []model.MediaEntry, opts model.DownloadOptions) ([]string, error) {
	if err := model.Validate(opts); err != nil {
		return nil, err
	}
	if len(entries) == 0 {
		return nil, errors.New("seçili öğe yok")
	}

	ids := make([]string, 0, len(entries))
	staged := make([]downloadTask, 0, len(entries))

	d.mu.Lock()
	d.seq++
	batchID := fmt.Sprintf("batch-%d", d.seq)

	batch := &batchState{total: len(entries)}
	d.batches[batchID] = batch

	for _, e := range entries {
		d.seq++
		id := fmt.Sprintf("%s-%d", e.ID, d.seq)
		t := downloadTask{id: id, batchID: batchID, entry: e, opts: opts}
		d.tasks[id] = t
		staged = append(staged, t)
		ids = append(ids, id)
	}
	d.mu.Unlock()

	d.emitBatch(batchID, batch)

	for _, t := range staged {
		d.queue <- t
		d.emit(TaskProgress{TaskID: t.id, State: "queued", BatchID: t.batchID})
	}
	return ids, nil
}

func (d *DownloadService) Cancel(taskID string) {
	d.mu.Lock()
	d.canceled[taskID] = true
	cancel := d.cancels[taskID]
	d.mu.Unlock()
	if cancel != nil {
		cancel()
	}
	d.emit(TaskProgress{TaskID: taskID, State: "canceled"})
}

func (d *DownloadService) Retry(taskID string) error {
	d.mu.Lock()
	t, ok := d.tasks[taskID]
	if ok {
		delete(d.canceled, taskID)
	}
	d.mu.Unlock()
	if !ok {
		return fmt.Errorf("görev bulunamadı: %s", taskID)
	}
	d.queue <- t
	d.emit(TaskProgress{TaskID: taskID, State: "queued", BatchID: t.batchID})
	return nil
}

func (d *DownloadService) Reveal(path string) error {
	if runtime.GOOS != "darwin" {
		return errors.New("bu özellik yalnızca macOS'ta destekleniyor")
	}
	if path == "" {
		return errors.New("dosya yolu boş")
	}
	st, err := os.Stat(path)
	switch {
	case err == nil && st.IsDir():
		return exec.Command("open", path).Run()
	case err == nil:
		return exec.Command("open", "-R", path).Run()
	default:
		dir := filepath.Dir(path)
		if _, e := os.Stat(dir); e == nil {
			return exec.Command("open", dir).Run()
		}
		return fmt.Errorf("dosya bulunamadı: %s", path)
	}
}

func (d *DownloadService) worker() {
	for t := range d.queue {
		d.mu.Lock()
		skip := d.canceled[t.id]
		d.mu.Unlock()
		if skip {
			continue
		}
		d.run(t)
	}
}

func (d *DownloadService) run(t downloadTask) {
	ctx, cancel := context.WithCancel(context.Background())
	d.mu.Lock()
	d.cancels[t.id] = cancel
	d.mu.Unlock()

	defer func() {
		cancel()
		d.mu.Lock()
		delete(d.cancels, t.id)
		d.mu.Unlock()
	}()

	var fm sync.Mutex
	lastFile := ""

	started := time.Now()
	cmd := engine.BuildCommand(t.opts).ProgressFunc(300*time.Millisecond, func(p ytdlp.ProgressUpdate) {
		fm.Lock()
		if p.Filename != "" {
			lastFile = p.Filename
		}
		fm.Unlock()

		total := p.TotalBytes
		pct := 0.0
		if total > 0 {
			pct = float64(p.DownloadedBytes) / float64(total) * 100
		}

		state := "downloading"
		if string(p.Status) == "finished" || string(p.Status) == "post_processing" {
			state = "converting"
			pct = 100
		}

		elapsed := time.Since(started).Seconds()
		speed := 0.0
		if elapsed > 0 {
			speed = float64(p.DownloadedBytes) / elapsed
		}

		eta := 0.0
		if p.ETA != nil {
			eta = p.ETA().Seconds()
		}

		d.emit(TaskProgress{
			TaskID:  t.id,
			State:   state,
			Percent: pct,
			Speed:   speed,
			ETA:     eta,
			BatchID: t.batchID,
		})
	})

	d.emit(TaskProgress{TaskID: t.id, State: "downloading", BatchID: t.batchID})

	_, err := cmd.Run(ctx, t.entry.URL)

	d.mu.Lock()
	wasCanceled := d.canceled[t.id]
	d.mu.Unlock()

	switch {
	case wasCanceled || ctx.Err() != nil:
		d.emit(TaskProgress{TaskID: t.id, State: "canceled", BatchID: t.batchID})
		d.recordBatchResult(t.batchID, false)
	case err != nil:
		d.emit(TaskProgress{TaskID: t.id, State: "error", Error: err.Error(), BatchID: t.batchID})
		d.recordBatchResult(t.batchID, false)
	default:
		fm.Lock()
		fp := lastFile
		fm.Unlock()
		if t.opts.Mode == "audio" && fp != "" {
			fp = strings.TrimSuffix(fp, filepath.Ext(fp)) + "." + t.opts.AudioFormat
		}
		d.emit(TaskProgress{
			TaskID:   t.id,
			State:    "done",
			Percent:  100,
			FilePath: fp,
			BatchID:  t.batchID,
		})
		d.recordBatchResult(t.batchID, true)
	}
}

func (d *DownloadService) recordBatchResult(batchID string, ok bool) {
	d.mu.Lock()
	batch := d.batches[batchID]
	d.mu.Unlock()
	if batch == nil {
		return
	}
	batch.mu.Lock()
	if ok {
		batch.completed++
	} else {
		batch.failed++
	}
	batch.mu.Unlock()
	d.emitBatch(batchID, batch)
}

func (d *DownloadService) emitBatch(batchID string, batch *batchState) {
	batch.mu.Lock()
	p := BatchProgress{
		BatchID:   batchID,
		Total:     batch.total,
		Completed: batch.completed,
		Current:   batch.completed + batch.failed,
		Failed:    batch.failed,
	}
	batch.mu.Unlock()

	if app := application.Get(); app != nil {
		app.Event.Emit("batch:progress", p)
	}
}

func (d *DownloadService) emit(p TaskProgress) {
	if app := application.Get(); app != nil {
		app.Event.Emit("task:progress", p)
	}
}
