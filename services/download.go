// ytdlp-studio:generated v1
// ytdlp-studio:download v3
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

	"github.com/wailsapp/wails/v3/pkg/application"
	"ytdlp-studio/internal/engine"
	"ytdlp-studio/internal/model"
)

type TaskProgress struct {
	TaskID     string  `json:"taskId"`
	State      string  `json:"state"`
	Percent    float64 `json:"percent"`
	Speed      float64 `json:"speedBps"`
	ETA        float64 `json:"etaSec"`
	Error      string  `json:"error,omitempty"`
	FilePath   string  `json:"filePath,omitempty"`
	BatchID    string  `json:"batchId,omitempty"`
	BatchTitle string  `json:"batchTitle,omitempty"`
}

type BatchInfo struct {
	Title string `json:"title"`
	ID    string `json:"id"`
	Kind  string `json:"kind"`
}

type BatchProgress struct {
	BatchID   string  `json:"batchId"`
	Title     string  `json:"title"`
	Kind      string  `json:"kind"`
	Total     int     `json:"total"`
	Completed int     `json:"completed"`
	Failed    int     `json:"failed"`
	Current   int     `json:"current"`
	Percent   float64 `json:"percent"`
	Done      bool    `json:"done"`
}

type LogLine struct {
	Time   string `json:"time"`
	TaskID string `json:"taskId,omitempty"`
	Text   string `json:"text"`
}

type downloadTask struct {
	id      string
	batchID string
	title   string
	entry   model.MediaEntry
	opts    model.DownloadOptions
	pl      engine.PlaylistContext
}

type batchState struct {
	title     string
	kind      string
	total     int
	completed int
	failed    int
	ids       []string
	states    map[string]string
	percent   map[string]float64
	lastEmit  time.Time
}

func (b *batchState) snapshot(id string) BatchProgress {
	sum := 0.0
	for _, tid := range b.ids {
		sum += b.percent[tid]
	}
	pct := 0.0
	if b.total > 0 {
		pct = sum / float64(b.total)
	}
	if pct > 100 {
		pct = 100
	}
	cur := b.completed + b.failed
	done := cur >= b.total
	if done && b.failed == 0 {
		pct = 100
	}
	return BatchProgress{
		BatchID: id, Title: b.title, Kind: b.kind, Total: b.total,
		Completed: b.completed, Failed: b.failed, Current: cur,
		Percent: pct, Done: done,
	}
}

type DownloadService struct {
	mu        sync.Mutex
	queue     chan downloadTask
	cancels   map[string]context.CancelFunc
	canceled  map[string]bool
	paused    map[string]bool
	tasks     map[string]downloadTask
	states    map[string]string
	percents  map[string]float64
	batches   map[string]*batchState
	taskBatch map[string]string
	seq       int
	batchSeq  int
}

func NewDownloadService(workers int) *DownloadService {
	if workers < 1 {
		workers = 1
	}
	d := &DownloadService{
		queue:     make(chan downloadTask, 8192),
		cancels:   map[string]context.CancelFunc{},
		canceled:  map[string]bool{},
		paused:    map[string]bool{},
		tasks:     map[string]downloadTask{},
		states:    map[string]string{},
		percents:  map[string]float64{},
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

func (d *DownloadService) PickFile() (string, error) {
	return application.Get().Dialog.OpenFile().
		SetTitle("Dosya Seç").
		CanChooseDirectories(false).
		CanChooseFiles(true).
		PromptForSingleSelection()
}

func (d *DownloadService) Enqueue(entries []model.MediaEntry, opts model.DownloadOptions, batch BatchInfo) ([]string, error) {
	if err := model.Validate(opts); err != nil {
		return nil, err
	}
	if len(entries) == 0 {
		return nil, errors.New("seçili öğe yok")
	}
	kind := batch.Kind
	if kind != "playlist" {
		kind = "file"
	}
	if len(entries) > 1 {
		kind = "playlist"
	}
	title := strings.TrimSpace(batch.Title)
	if title == "" {
		title = strings.TrimSpace(entries[0].Title)
	}
	if title == "" {
		title = "İndirme"
	}
	pl := engine.PlaylistContext{IsPlaylist: kind == "playlist", Title: title, ID: batch.ID}

	ids := make([]string, 0, len(entries))
	staged := make([]downloadTask, 0, len(entries))

	d.mu.Lock()
	d.batchSeq++
	bid := fmt.Sprintf("batch-%d", d.batchSeq)
	b := &batchState{
		title: title, kind: kind, total: len(entries),
		states: map[string]string{}, percent: map[string]float64{},
	}
	d.batches[bid] = b
	for i, e := range entries {
		if e.Index <= 0 {
			e.Index = i + 1
		}
		e.URL = engine.EntryURL(e.ID, e.URL)
		d.seq++
		id := fmt.Sprintf("%s-%d", e.ID, d.seq)
		t := downloadTask{id: id, batchID: bid, title: e.Title, entry: e, opts: opts, pl: pl}
		d.tasks[id] = t
		d.taskBatch[id] = bid
		d.percents[id] = 0
		b.ids = append(b.ids, id)
		b.percent[id] = 0
		staged = append(staged, t)
		ids = append(ids, id)
	}
	snap := b.snapshot(bid)
	d.mu.Unlock()

	d.emitBatch(snap)
	for _, t := range staged {
		d.queue <- t
		d.emit(TaskProgress{TaskID: t.id, State: "queued", BatchID: bid, BatchTitle: title})
	}
	return ids, nil
}

func (d *DownloadService) activeIDs() []string {
	d.mu.Lock()
	defer d.mu.Unlock()
	var out []string
	for id, st := range d.states {
		if st == "queued" || st == "downloading" || st == "converting" {
			out = append(out, id)
		}
	}
	return out
}

func (d *DownloadService) Cancel(taskID string) {
	d.mu.Lock()
	st := d.states[taskID]
	if st == "done" || st == "error" || st == "canceled" {
		d.mu.Unlock()
		return
	}
	d.canceled[taskID] = true
	cancel := d.cancels[taskID]
	bid := d.taskBatch[taskID]
	d.mu.Unlock()
	if cancel != nil {
		cancel()
	}
	d.finish(taskID, "canceled", "", "")
	d.recordBatch(bid)
}

func (d *DownloadService) Pause(taskID string) {
	d.mu.Lock()
	st := d.states[taskID]
	if st != "queued" && st != "downloading" && st != "converting" {
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
	d.finish(taskID, "paused", "", "")
}

func (d *DownloadService) Resume(taskID string) error {
	d.mu.Lock()
	t, ok := d.tasks[taskID]
	bid := d.taskBatch[taskID]
	var snap *BatchProgress
	if ok {
		delete(d.canceled, taskID)
		delete(d.paused, taskID)
		d.percents[taskID] = 0
		if b := d.batches[bid]; b != nil {
			switch b.states[taskID] {
			case "done":
				if b.completed > 0 {
					b.completed--
				}
			case "error", "canceled":
				if b.failed > 0 {
					b.failed--
				}
			}
			delete(b.states, taskID)
			b.percent[taskID] = 0
			s := b.snapshot(bid)
			snap = &s
		}
	}
	d.mu.Unlock()
	if !ok {
		return fmt.Errorf("görev bulunamadı: %s", taskID)
	}
	d.queue <- t
	d.emit(TaskProgress{TaskID: taskID, State: "queued", BatchID: bid, BatchTitle: t.title})
	if snap != nil {
		d.emitBatch(*snap)
	}
	return nil
}

func (d *DownloadService) Retry(taskID string) error { return d.Resume(taskID) }

func (d *DownloadService) PauseAll() {
	for _, id := range d.activeIDs() {
		d.Pause(id)
	}
}

func (d *DownloadService) ResumeAll() {
	d.mu.Lock()
	var ids []string
	for id, st := range d.states {
		if st == "paused" {
			ids = append(ids, id)
		}
	}
	d.mu.Unlock()
	for _, id := range ids {
		_ = d.Resume(id)
	}
}

func (d *DownloadService) CancelAll() {
	for _, id := range d.activeIDs() {
		d.Cancel(id)
	}
}

func (d *DownloadService) Remove(taskID string) {
	d.mu.Lock()
	cancel := d.cancels[taskID]
	delete(d.tasks, taskID)
	delete(d.states, taskID)
	delete(d.canceled, taskID)
	delete(d.paused, taskID)
	delete(d.cancels, taskID)
	delete(d.percents, taskID)
	delete(d.taskBatch, taskID)
	d.mu.Unlock()
	if cancel != nil {
		cancel()
	}
}

func (d *DownloadService) ClearFinished() {
	d.mu.Lock()
	for id, st := range d.states {
		switch st {
		case "done", "canceled", "error":
			delete(d.tasks, id)
			delete(d.states, id)
			delete(d.canceled, id)
			delete(d.paused, id)
			delete(d.cancels, id)
			delete(d.percents, id)
			delete(d.taskBatch, id)
		}
	}
	d.mu.Unlock()
}

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
	d.percents = map[string]float64{}
	d.paused = map[string]bool{}
	d.taskBatch = map[string]string{}
	d.batches = map[string]*batchState{}
	d.mu.Unlock()
	for _, c := range cancels {
		c()
	}
}

func (d *DownloadService) Reveal(path string) error {
	if path == "" {
		return errors.New("dosya yolu boş")
	}
	target, selectFile := path, false
	if st, err := os.Stat(path); err != nil {
		dir := filepath.Dir(path)
		if _, e := os.Stat(dir); e != nil {
			return fmt.Errorf("dosya bulunamadı: %s", path)
		}
		target = dir
	} else if !st.IsDir() {
		selectFile = true
	}
	switch runtime.GOOS {
	case "darwin":
		if selectFile {
			return exec.Command("open", "-R", target).Run()
		}
		return exec.Command("open", target).Run()
	case "windows":
		if selectFile {
			return exec.Command("explorer.exe", "/select,", target).Run()
		}
		return exec.Command("explorer.exe", target).Run()
	default:
		if selectFile {
			target = filepath.Dir(target)
		}
		return exec.Command("xdg-open", target).Run()
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

func subExt(ext string) bool {
	switch strings.ToLower(ext) {
	case ".srt", ".vtt", ".ass", ".ssa", ".lrc", ".ttml", ".sbv":
		return true
	}
	return false
}

func (d *DownloadService) finalPath(t downloadTask, lastFile string) string {
	if lastFile == "" {
		return t.opts.OutputDir
	}
	switch t.opts.Mode {
	case "audio":
		p := strings.TrimSuffix(lastFile, filepath.Ext(lastFile)) + "." + t.opts.AudioFormat
		if _, err := os.Stat(p); err == nil {
			return p
		}
		return lastFile
	case "subtitle":
		base := strings.TrimSuffix(lastFile, filepath.Ext(lastFile))
		matches, _ := filepath.Glob(base + ".*")
		for _, m := range matches {
			if subExt(filepath.Ext(m)) {
				return m
			}
		}
		return filepath.Dir(lastFile)
	default:
		return lastFile
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

	hooks := engine.Hooks{
		OnProgress: func(p engine.Progress) {
			pct := 0.0
			if p.Total > 0 {
				pct = p.Downloaded / p.Total * 100
			}
			if pct > 100 {
				pct = 100
			}
			if p.Filename != "" {
				fm.Lock()
				lastFile = p.Filename
				fm.Unlock()
			}
			d.emit(TaskProgress{
				TaskID: t.id, State: "downloading", Percent: pct,
				Speed: p.Speed, ETA: p.ETA, BatchID: t.batchID, BatchTitle: t.title,
			})
			d.touchBatch(t.id, pct)
		},
		OnPostprocess: func(name string) {
			d.emit(TaskProgress{
				TaskID: t.id, State: "converting", Percent: 100,
				BatchID: t.batchID, BatchTitle: t.title,
			})
			d.log(t.id, "postprocess: "+name)
		},
		OnFile: func(p string) {
			fm.Lock()
			lastFile = p
			fm.Unlock()
		},
		OnLog: func(line string) { d.log(t.id, line) },
	}

	d.emit(TaskProgress{TaskID: t.id, State: "downloading", BatchID: t.batchID, BatchTitle: t.title})
	err := engine.RunDownload(ctx, engine.BuildArgs(t.opts, t.entry, t.pl), engine.EntryURL(t.entry.ID, t.entry.URL), hooks)

	d.mu.Lock()
	wasCanceled := d.canceled[t.id]
	wasPaused := d.paused[t.id]
	d.mu.Unlock()

	fm.Lock()
	lf := lastFile
	fm.Unlock()

	switch {
	case wasPaused:
		d.finish(t.id, "paused", "", "")
	case wasCanceled || ctx.Err() != nil:
		d.finish(t.id, "canceled", "", "")
		d.recordBatch(t.batchID)
	case err != nil:
		d.finish(t.id, "error", err.Error(), "")
		d.recordBatch(t.batchID)
	default:
		d.finish(t.id, "done", "", d.finalPath(t, lf))
		d.recordBatch(t.batchID)
	}
}

func (d *DownloadService) finish(taskID, state, errMsg, filePath string) {
	d.mu.Lock()
	t, ok := d.tasks[taskID]
	pct := d.percents[taskID]
	if state == "done" {
		pct = 100
		d.percents[taskID] = 100
	}
	d.mu.Unlock()
	if !ok {
		return
	}
	d.emit(TaskProgress{
		TaskID: taskID, State: state, Percent: pct, Error: errMsg, FilePath: filePath,
		BatchID: t.batchID, BatchTitle: t.title,
	})
}

func (d *DownloadService) touchBatch(taskID string, pct float64) {
	d.mu.Lock()
	d.percents[taskID] = pct
	b := d.batches[d.taskBatch[taskID]]
	var snap *BatchProgress
	if b != nil {
		b.percent[taskID] = pct
		if time.Since(b.lastEmit) >= 400*time.Millisecond {
			b.lastEmit = time.Now()
			s := b.snapshot(d.taskBatch[taskID])
			snap = &s
		}
	}
	d.mu.Unlock()
	if snap != nil {
		d.emitBatch(*snap)
	}
}

func (d *DownloadService) recordBatch(batchID string) {
	if batchID == "" {
		return
	}
	d.mu.Lock()
	b := d.batches[batchID]
	var snap *BatchProgress
	if b != nil {
		b.completed, b.failed = 0, 0
		for _, id := range b.ids {
			switch b.states[id] {
			case "done":
				b.completed++
			case "error", "canceled":
				b.failed++
			}
		}
		s := b.snapshot(batchID)
		snap = &s
	}
	d.mu.Unlock()
	if snap != nil {
		d.emitBatch(*snap)
		if snap.Done {
			if app := application.Get(); app != nil {
				app.Event.Emit("batch:completed", *snap)
			}
		}
	}
}

func (d *DownloadService) emit(p TaskProgress) {
	d.mu.Lock()
	if _, ok := d.tasks[p.TaskID]; !ok {
		d.mu.Unlock()
		return
	}
	d.states[p.TaskID] = p.State
	if b := d.batches[d.taskBatch[p.TaskID]]; b != nil {
		switch p.State {
		case "done", "error", "canceled":
			b.states[p.TaskID] = p.State
			if p.State == "done" {
				b.percent[p.TaskID] = 100
			}
		}
	}
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

func (d *DownloadService) log(taskID, text string) {
	if app := application.Get(); app != nil {
		app.Event.Emit("log:line", LogLine{
			Time: time.Now().Format("15:04:05"), TaskID: taskID, Text: text,
		})
	}
}
