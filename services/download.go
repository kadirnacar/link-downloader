// ytdlp-studio:generated v1
// ytdlp-studio:download-progress v2
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

// TaskProgress tek bir dosyanın indirme durumunu taşır.
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

// BatchProgress bir toplu indirmenin genel ilerlemesini taşır.
// Current = Completed + Failed (başarısızlar da ilerlemeye dahildir).
type BatchProgress struct {
	BatchID   string `json:"batchId"`
	Total     int    `json:"total"`
	Completed int    `json:"completed"`
	Failed    int    `json:"failed"`
	Current   int    `json:"current"`
	Done      bool   `json:"done"`
}

type downloadTask struct {
	id      string
	batchID string
	entry   model.MediaEntry
	opts    model.DownloadOptions
}

type batchState struct {
	total     int
	completed int
	failed    int
	mu        sync.Mutex
}

func (b *batchState) snapshot(id string) BatchProgress {
	b.mu.Lock()
	defer b.mu.Unlock()
	current := b.completed + b.failed
	return BatchProgress{
		BatchID:   id,
		Total:     b.total,
		Completed: b.completed,
		Failed:    b.failed,
		Current:   current,
		Done:      current >= b.total,
	}
}

type DownloadService struct {
	mu       sync.Mutex
	queue    chan downloadTask
	cancels  map[string]context.CancelFunc
	canceled map[string]bool
	paused   map[string]bool
	tasks    map[string]downloadTask
	states   map[string]string
	batches  map[string]*batchState
	taskBatch map[string]string
	seq      int
}

func NewDownloadService(workers int) *DownloadService {
	if workers < 1 {
		workers = 1
	}
	d := &DownloadService{
		queue:     make(chan downloadTask, 4096),
		cancels:   map[string]context.CancelFunc{},
		canceled:  map[string]bool{},
		paused:    map[string]bool{},
		tasks:     map[string]downloadTask{},
		states:    map[string]string{},
		batches:   map[string]*batchState{},
		taskBatch: map[string]string{},
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

// Enqueue seçili girişleri kuyruğa alır.
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
		d.taskBatch[id] = batchID
		staged = append(staged, t)
		ids = append(ids, id)
	}
	snap := batch.snapshot(batchID)
	d.mu.Unlock()

	d.emitBatch(snap)

	for _, t := range staged {
		d.queue <- t
		d.emit(TaskProgress{TaskID: t.id, State: "queued", BatchID: t.batchID})
	}
	return ids, nil
}

// Cancel aktif görevi iptal eder.
func (d *DownloadService) Cancel(taskID string) {
	d.mu.Lock()
	st := d.states[taskID]
	if st == "done" || st == "error" || st == "canceled" {
		d.mu.Unlock()
		return
	}
	d.canceled[taskID] = true
	cancel := d.cancels[taskID]
	d.mu.Unlock()
	if cancel != nil {
		cancel()
	}
	d.emit(TaskProgress{TaskID: taskID, State: "canceled", BatchID: d.batchOf(taskID)})
}

// Pause aktif görevi duraklatır. yt-dlp kaldığı yerden devam edebildiği için
// Resume ile indirme mümkün olduğunca mevcut dosya üzerinden sürer.
func (d *DownloadService) Pause(taskID string) {
	d.mu.Lock()
	st := d.states[taskID]
	if st == "done" || st == "error" || st == "canceled" || st == "paused" {
		d.mu.Unlock()
		return
	}
	d.paused[taskID] = true
	d.canceled[taskID] = true
	cancel := d.cancels[taskID]
	d.mu.Unlock()
	if cancel != nil {
		cancel()
	}
	d.emit(TaskProgress{TaskID: taskID, State: "paused", BatchID: d.batchOf(taskID)})
}

// Resume duraklatılmış veya başarısız görevi yeniden kuyruğa alır.
func (d *DownloadService) Resume(taskID string) error {
	d.mu.Lock()
	t, ok := d.tasks[taskID]
	if ok {
		delete(d.canceled, taskID)
		delete(d.paused, taskID)
	}
	d.mu.Unlock()
	if !ok {
		return fmt.Errorf("görev bulunamadı: %s", taskID)
	}
	d.queue <- t
	d.emit(TaskProgress{TaskID: taskID, State: "queued", BatchID: t.batchID})
	return nil
}

// Retry, Resume ile aynı davranışı sunar (hata/iptal sonrası yeniden dener).
func (d *DownloadService) Retry(taskID string) error {
	return d.Resume(taskID)
}

// Remove görevi listeden ve backend kaydından siler; aktifse iptal eder.
func (d *DownloadService) Remove(taskID string) {
	d.mu.Lock()
	cancel := d.cancels[taskID]
	delete(d.tasks, taskID)
	delete(d.states, taskID)
	delete(d.canceled, taskID)
	delete(d.paused, taskID)
	delete(d.cancels, taskID)
	delete(d.taskBatch, taskID)
	d.mu.Unlock()
	if cancel != nil {
		cancel()
	}
}

// ClearFinished bitmiş görevleri backend kaydından temizler.
func (d *DownloadService) ClearFinished() {
	d.mu.Lock()
	for id := range d.tasks {
		switch d.states[id] {
		case "done", "canceled", "error":
			delete(d.tasks, id)
			delete(d.states, id)
			delete(d.canceled, id)
			delete(d.paused, id)
			delete(d.cancels, id)
			delete(d.taskBatch, id)
		}
	}
	d.mu.Unlock()
}

// CancelAll aktif/bekleyen tüm görevleri iptal eder.
func (d *DownloadService) CancelAll() {
	d.mu.Lock()
	var cancels []context.CancelFunc
	for id := range d.tasks {
		st := d.states[id]
		if st == "done" || st == "error" || st == "canceled" {
			continue
		}
		d.canceled[id] = true
		if c := d.cancels[id]; c != nil {
			cancels = append(cancels, c)
		}
	}
	d.mu.Unlock()
	for _, c := range cancels {
		c()
	}
}

// ClearAll tüm görevleri iptal eder ve kayıtları temizler.
func (d *DownloadService) ClearAll() {
	d.mu.Lock()
	var cancels []context.CancelFunc
	for id := range d.tasks {
		d.canceled[id] = true
		if c := d.cancels[id]; c != nil {
			cancels = append(cancels, c)
		}
	}
	d.tasks = map[string]downloadTask{}
	d.states = map[string]string{}
	d.paused = map[string]bool{}
	d.taskBatch = map[string]string{}
	d.mu.Unlock()
	for _, c := range cancels {
		c()
	}
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

func (d *DownloadService) batchOf(taskID string) string {
	d.mu.Lock()
	defer d.mu.Unlock()
	return d.taskBatch[taskID]
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

	cmd := engine.BuildCommand(t.opts, t.entry).ProgressFunc(300*time.Millisecond, func(p ytdlp.ProgressUpdate) {
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

		speed := 0.0
		if el := time.Since(started).Seconds(); el > 0 {
			speed = float64(p.DownloadedBytes) / el
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
	wasPaused := d.paused[t.id]
	d.mu.Unlock()

	switch {
	case wasPaused:
		d.emit(TaskProgress{TaskID: t.id, State: "paused", BatchID: t.batchID})
	case wasCanceled || ctx.Err() != nil:
		d.emit(TaskProgress{TaskID: t.id, State: "canceled", BatchID: t.batchID})
		d.recordBatch(t.batchID, false)
	case err != nil:
		d.emit(TaskProgress{TaskID: t.id, State: "error", Error: err.Error(), BatchID: t.batchID})
		d.recordBatch(t.batchID, false)
	default:
		fm.Lock()
		fp := lastFile
		fm.Unlock()
		if t.opts.Mode == "audio" && fp != "" {
			fp = strings.TrimSuffix(fp, filepath.Ext(fp)) + "." + t.opts.AudioFormat
		}
		d.emit(TaskProgress{TaskID: t.id, State: "done", Percent: 100, FilePath: fp, BatchID: t.batchID})
		d.recordBatch(t.batchID, true)
	}
}

// recordBatch batch sayacını günceller; bitişte batch:completed yayınlar.
func (d *DownloadService) recordBatch(batchID string, success bool) {
	if batchID == "" {
		return
	}
	d.mu.Lock()
	b := d.batches[batchID]
	d.mu.Unlock()
	if b == nil {
		return
	}

	b.mu.Lock()
	if success {
		b.completed++
	} else {
		b.failed++
	}
	b.mu.Unlock()

	snap := b.snapshot(batchID)
	d.emitBatch(snap)
	if snap.Done {
		d.emitBatchCompleted(snap)
	}
}

// emit, task durumunu yayınlar. Temizlenmiş görevler için emit yapılmaz.
func (d *DownloadService) emit(p TaskProgress) {
	d.mu.Lock()
	if _, ok := d.tasks[p.TaskID]; !ok {
		d.mu.Unlock()
		return
	}
	d.states[p.TaskID] = p.State
	d.mu.Unlock()

	if app := application.Get(); app != nil {
		app.Event.Emit("task:progress", p)
	}
}

func (d *DownloadService) emitBatch(p BatchProgress) {
	if app := application.Get(); app != nil {
		app.Event.Emit("batch:progress", p)
	}
}

func (d *DownloadService) emitBatchCompleted(p BatchProgress) {
	if app := application.Get(); app != nil {
		app.Event.Emit("batch:completed", p)
	}
}
