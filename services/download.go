// ytdlp-studio:generated v1
// ytdlp-studio:download v5
package services

import (
	"context"
	"errors"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
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
	id         string
	batchID    string
	batchTitle string
	title      string
	attempt    uint64
	entry      model.MediaEntry
	opts       model.DownloadOptions
	pl         engine.PlaylistContext
}

type taskRunLock struct {
	mu   sync.Mutex
	refs int
}

type batchState struct {
	title    string
	kind     string
	total    int
	ids      []string
	states   map[string]string
	percent  map[string]float64
	lastEmit time.Time
}

// snapshot çağrılırken d.mu KİLİTLİ olmalıdır.
func (b *batchState) snapshot(id string) BatchProgress {
	completed, failed, sum := 0, 0, 0.0
	for _, tid := range b.ids {
		switch b.states[tid] {
		case "done":
			completed++
		case "error", "canceled":
			failed++
		}
		sum += b.percent[tid]
	}
	pct := 0.0
	if b.total > 0 {
		pct = sum / float64(b.total)
	}
	if pct > 100 {
		pct = 100
	}
	cur := completed + failed
	done := b.total > 0 && cur >= b.total
	if done && failed == 0 {
		pct = 100
	}
	return BatchProgress{
		BatchID: id, Title: b.title, Kind: b.kind, Total: b.total,
		Completed: completed, Failed: failed, Current: cur, Percent: pct, Done: done,
	}
}

type DownloadService struct {
	mu             sync.Mutex
	queue          chan downloadTask
	store          *queueStore
	persistMu      sync.Mutex
	queueOrder     map[string]uint64
	queueSequence  uint64
	lastPersistAt  time.Time
	workerCtx      context.Context
	workerCancel   context.CancelFunc
	workerWG       sync.WaitGroup
	shutdownOnce   sync.Once
	closed         bool
	runLocks       map[string]*taskRunLock
	cancels        map[string]context.CancelFunc
	cancelAttempts map[string]uint64
	attempts       map[string]uint64
	canceled       map[string]bool
	paused         map[string]bool
	tasks          map[string]downloadTask
	states         map[string]string
	percents       map[string]float64
	files          map[string]string
	errors         map[string]string
	batches        map[string]*batchState
	taskBatch      map[string]string
	seq            int
	batchSeq       int
}

func NewDownloadService(workers int) *DownloadService {
	return newDownloadService(workers, nil, queueSnapshot{Version: queueStoreVersion})
}

// NewPersistentDownloadService restores the user's queue before workers start.
// A corrupt/unreadable queue is reported instead of silently discarding tasks.
func NewPersistentDownloadService(workers int) (*DownloadService, error) {
	store, err := newQueueStore()
	if err != nil {
		return nil, err
	}
	snapshot, err := store.Load()
	if err != nil {
		return nil, err
	}
	return newDownloadService(workers, store, snapshot), nil
}

func newDownloadService(workers int, store *queueStore, snapshot queueSnapshot) *DownloadService {
	if workers < 1 {
		workers = 1
	}
	if workers > 8 {
		workers = 8
	}
	queueCapacity := 8192
	if len(snapshot.Tasks)+64 > queueCapacity {
		queueCapacity = len(snapshot.Tasks) + 64
	}
	workerCtx, workerCancel := context.WithCancel(context.Background())
	d := &DownloadService{
		queue:          make(chan downloadTask, queueCapacity),
		store:          store,
		queueOrder:     map[string]uint64{},
		workerCtx:      workerCtx,
		workerCancel:   workerCancel,
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
	d.restoreQueue(snapshot)
	for i := 0; i < workers; i++ {
		d.workerWG.Add(1)
		go func() { defer d.workerWG.Done(); d.worker() }()
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

func taskURL(e model.MediaEntry) string {
	if u := strings.TrimSpace(e.URL); u != "" {
		return u
	}
	if id := strings.TrimSpace(e.ID); id != "" {
		return "https://www.youtube.com/watch?v=" + id
	}
	return ""
}

func validateQueuedTask(t downloadTask) error {
	if !t.entry.Available {
		return errors.New("kayıtlı öğe indirilebilir durumda değil")
	}
	if err := model.Validate(t.opts); err != nil {
		return fmt.Errorf("kayıtlı indirme ayarları geçersiz: %w", err)
	}
	entryID := strings.TrimSpace(t.entry.ID)
	parsed, err := (&AnalyzeService{}).ParseURL(taskURL(t.entry))
	if err != nil || entryID == "" || parsed.VideoID == "" || parsed.VideoID != entryID {
		return errors.New("kayıtlı indirme URL'si geçersiz veya desteklenmiyor")
	}
	return nil
}

func (d *DownloadService) Enqueue(entries []model.MediaEntry, opts model.DownloadOptions, batch BatchInfo) ([]string, error) {
	if err := model.Validate(opts); err != nil {
		return nil, err
	}
	if len(entries) == 0 {
		return nil, errors.New("seçili öğe yok")
	}
	for i, entry := range entries {
		if !entry.Available {
			return nil, fmt.Errorf("%d. öğe indirilebilir durumda değil", i+1)
		}
		u := taskURL(entry)
		if u == "" {
			return nil, fmt.Errorf("%d. öğenin indirme URL'si yok", i+1)
		}
		parsed, parseErr := (&AnalyzeService{}).ParseURL(u)
		entryID := strings.TrimSpace(entry.ID)
		if parseErr != nil || parsed.VideoID == "" || entryID == "" || entryID != parsed.VideoID {
			return nil, fmt.Errorf("%d. öğe desteklenmeyen bir YouTube video URL'si içeriyor", i+1)
		}
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
	if d.closed {
		d.mu.Unlock()
		return nil, errors.New("uygulama kapanıyor; yeni görev eklenemez")
	}
	d.batchSeq++
	bid := fmt.Sprintf("batch-%d", d.batchSeq)
	b := &batchState{
		title: title, kind: kind, total: len(entries),
		states: map[string]string{}, percent: map[string]float64{},
	}
	d.batches[bid] = b
	for i, e := range entries {
		e.ID = strings.TrimSpace(e.ID)
		if e.Index <= 0 {
			e.Index = i + 1
		}
		e.URL = taskURL(e)
		d.seq++
		id := fmt.Sprintf("%s-%d", e.ID, d.seq)
		t := downloadTask{id: id, batchID: bid, batchTitle: title, title: e.Title, attempt: 1, entry: e, opts: opts, pl: pl}
		d.tasks[id] = t
		d.queueSequence++
		d.queueOrder[id] = d.queueSequence
		d.attempts[id] = t.attempt
		d.states[id] = "queued"
		d.taskBatch[id] = bid
		d.percents[id] = 0
		b.ids = append(b.ids, id)
		b.percent[id] = 0
		staged = append(staged, t)
		ids = append(ids, id)
	}
	snap := b.snapshot(bid)
	d.mu.Unlock()

	if err := d.persistQueue(); err != nil {
		d.mu.Lock()
		for _, t := range staged {
			d.deleteTaskLocked(t.id)
		}
		delete(d.batches, bid)
		d.mu.Unlock()
		return nil, fmt.Errorf("kuyruk diske kaydedilemedi; görevler eklenmedi: %w", err)
	}
	d.emitBatch(snap)
	for _, t := range staged {
		d.emitAttempt(TaskProgress{TaskID: t.id, State: "queued", BatchID: bid, BatchTitle: title}, t.attempt)
		d.queue <- t
	}
	return ids, nil
}

// Snapshot UI'ın backend gerçeğiyle eşitlenmesini sağlar.
func (d *DownloadService) Snapshot() []TaskProgress {
	d.mu.Lock()
	defer d.mu.Unlock()
	out := make([]TaskProgress, 0, len(d.tasks))
	ids := make([]string, 0, len(d.tasks))
	for id := range d.tasks {
		ids = append(ids, id)
	}
	sort.Slice(ids, func(i, j int) bool { return d.queueOrder[ids[i]] < d.queueOrder[ids[j]] })
	for _, id := range ids {
		t := d.tasks[id]
		st := d.states[id]
		if st == "" {
			st = "queued"
		}
		out = append(out, TaskProgress{
			TaskID: id, State: st, Percent: d.percents[id],
			Error: d.errors[id], FilePath: d.files[id],
			BatchID: t.batchID, BatchTitle: t.batchTitle,
		})
	}
	return out
}

func (d *DownloadService) Batches() []BatchProgress {
	d.mu.Lock()
	defer d.mu.Unlock()
	out := make([]BatchProgress, 0, len(d.batches))
	ids := make([]string, 0, len(d.batches))
	for id := range d.batches {
		ids = append(ids, id)
	}
	sort.Slice(ids, func(i, j int) bool { return batchNumber(ids[i]) < batchNumber(ids[j]) })
	for _, id := range ids {
		out = append(out, d.batches[id].snapshot(id))
	}
	return out
}

func (d *DownloadService) idsByState(states ...string) []string {
	want := map[string]bool{}
	for _, s := range states {
		want[s] = true
	}
	d.mu.Lock()
	defer d.mu.Unlock()
	var out []string
	for id := range d.tasks {
		st := d.states[id]
		if st == "" {
			st = "queued"
		}
		if want[st] {
			out = append(out, id)
		}
	}
	sort.Slice(out, func(i, j int) bool { return d.queueOrder[out[i]] < d.queueOrder[out[j]] })
	return out
}

func (d *DownloadService) Cancel(taskID string) {
	d.mu.Lock()
	if _, ok := d.tasks[taskID]; !ok {
		d.mu.Unlock()
		return
	}
	switch d.states[taskID] {
	case "done", "error", "canceled":
		d.mu.Unlock()
		return
	}
	d.canceled[taskID] = true
	delete(d.paused, taskID)
	cancel := d.cancels[taskID]
	attempt := d.attempts[taskID]
	bid := d.taskBatch[taskID]
	d.mu.Unlock()

	if cancel != nil {
		cancel()
	}
	if d.finish(taskID, attempt, "canceled", "", "") {
		d.syncBatch(bid)
	}
}

func (d *DownloadService) Pause(taskID string) {
	d.mu.Lock()
	if _, ok := d.tasks[taskID]; !ok {
		d.mu.Unlock()
		return
	}
	switch d.states[taskID] {
	case "done", "error", "canceled", "paused":
		d.mu.Unlock()
		return
	}
	d.paused[taskID] = true
	d.canceled[taskID] = true
	cancel := d.cancels[taskID]
	attempt := d.attempts[taskID]
	bid := d.taskBatch[taskID]
	d.mu.Unlock()

	if cancel != nil {
		cancel()
	}
	if d.finish(taskID, attempt, "paused", "", "") {
		d.syncBatch(bid)
	}
}

func (d *DownloadService) Resume(taskID string) error {
	d.mu.Lock()
	if d.closed {
		d.mu.Unlock()
		return errors.New("uygulama kapanıyor; görev sürdürülemez")
	}
	t, ok := d.tasks[taskID]
	if !ok {
		d.mu.Unlock()
		return fmt.Errorf("görev bulunamadı: %s", taskID)
	}
	if err := validateQueuedTask(t); err != nil {
		d.mu.Unlock()
		return err
	}
	switch d.states[taskID] {
	case "paused", "error", "canceled":
	default:
		state := d.states[taskID]
		d.mu.Unlock()
		return fmt.Errorf("%s durumundaki görev yeniden başlatılamaz", state)
	}
	oldAttempt := d.attempts[taskID]
	oldState := d.states[taskID]
	oldPercent := d.percents[taskID]
	oldError, hadError := d.errors[taskID]
	oldOrder := d.queueOrder[taskID]
	t.attempt = oldAttempt + 1
	d.attempts[taskID] = t.attempt
	d.tasks[taskID] = t
	d.states[taskID] = "queued"
	d.queueSequence++
	d.queueOrder[taskID] = d.queueSequence
	delete(d.canceled, taskID)
	delete(d.paused, taskID)
	delete(d.errors, taskID)
	d.percents[taskID] = 0
	bid := d.taskBatch[taskID]
	var snap *BatchProgress
	if b := d.batches[bid]; b != nil {
		delete(b.states, taskID)
		b.percent[taskID] = 0
		s := b.snapshot(bid)
		snap = &s
	}
	d.mu.Unlock()

	if err := d.persistQueue(); err != nil {
		d.mu.Lock()
		if d.attempts[taskID] == t.attempt && d.states[taskID] == "queued" {
			t.attempt = oldAttempt
			d.tasks[taskID] = t
			d.attempts[taskID] = oldAttempt
			d.states[taskID] = oldState
			d.percents[taskID] = oldPercent
			d.queueOrder[taskID] = oldOrder
			if hadError {
				d.errors[taskID] = oldError
			}
			if b := d.batches[bid]; b != nil {
				b.percent[taskID] = oldPercent
				if oldState == "error" || oldState == "canceled" {
					b.states[taskID] = oldState
				}
			}
		}
		d.mu.Unlock()
		return fmt.Errorf("görev kuyruğu kaydedilemedi: %w", err)
	}
	d.emitAttempt(TaskProgress{TaskID: taskID, State: "queued", BatchID: bid, BatchTitle: t.batchTitle}, t.attempt)
	d.queue <- t
	if snap != nil {
		d.emitBatch(*snap)
	}
	return nil
}

func (d *DownloadService) Remove(taskID string) {
	d.mu.Lock()
	cancel := d.cancels[taskID]
	bid := d.taskBatch[taskID]
	delete(d.tasks, taskID)
	delete(d.queueOrder, taskID)
	delete(d.states, taskID)
	delete(d.canceled, taskID)
	delete(d.paused, taskID)
	delete(d.cancels, taskID)
	delete(d.percents, taskID)
	delete(d.files, taskID)
	delete(d.errors, taskID)
	delete(d.taskBatch, taskID)
	delete(d.attempts, taskID)
	delete(d.cancelAttempts, taskID)
	var snap *BatchProgress
	if b := d.batches[bid]; b != nil {
		var kept []string
		for _, id := range b.ids {
			if id != taskID {
				kept = append(kept, id)
			}
		}
		b.ids = kept
		delete(b.states, taskID)
		delete(b.percent, taskID)
		if b.total > 0 {
			b.total--
		}
		if len(b.ids) == 0 {
			delete(d.batches, bid)
		} else {
			s := b.snapshot(bid)
			snap = &s
		}
	}
	d.mu.Unlock()

	if cancel != nil {
		cancel()
	}
	d.persistQueueQuiet()
	if snap != nil {
		d.emitBatch(*snap)
	}
}

func (d *DownloadService) ClearFinished() {
	d.mu.Lock()
	affected := map[string]bool{}
	for id, st := range d.states {
		switch st {
		case "done", "canceled", "error":
			bid := d.taskBatch[id]
			if b := d.batches[bid]; b != nil {
				var kept []string
				for _, x := range b.ids {
					if x != id {
						kept = append(kept, x)
					}
				}
				b.ids = kept
				delete(b.states, id)
				delete(b.percent, id)
				if b.total > 0 {
					b.total--
				}
				affected[bid] = true
			}
			delete(d.tasks, id)
			delete(d.queueOrder, id)
			delete(d.states, id)
			delete(d.canceled, id)
			delete(d.paused, id)
			delete(d.cancels, id)
			delete(d.percents, id)
			delete(d.files, id)
			delete(d.errors, id)
			delete(d.taskBatch, id)
			delete(d.attempts, id)
			delete(d.cancelAttempts, id)
		}
	}
	var snaps []BatchProgress
	for bid := range affected {
		if b := d.batches[bid]; b != nil {
			if len(b.ids) == 0 {
				delete(d.batches, bid)
				continue
			}
			snaps = append(snaps, b.snapshot(bid))
		}
	}
	d.mu.Unlock()

	d.persistQueueQuiet()
	for _, s := range snaps {
		d.emitBatch(s)
	}
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
	d.queueOrder = map[string]uint64{}
	d.attempts = map[string]uint64{}
	d.cancelAttempts = map[string]uint64{}
	d.cancels = map[string]context.CancelFunc{}
	d.canceled = map[string]bool{}
	d.states = map[string]string{}
	d.percents = map[string]float64{}
	d.files = map[string]string{}
	d.errors = map[string]string{}
	d.paused = map[string]bool{}
	d.taskBatch = map[string]string{}
	d.batches = map[string]*batchState{}
	d.mu.Unlock()

	for _, c := range cancels {
		c()
	}
	d.persistQueueQuiet()
}

func (d *DownloadService) CancelAll() {
	for _, id := range d.idsByState("queued", "downloading", "converting", "paused") {
		d.Cancel(id)
	}
}

func (d *DownloadService) PauseAll() {
	for _, id := range d.idsByState("queued", "downloading", "converting") {
		d.Pause(id)
	}
}

func (d *DownloadService) ResumeAll() {
	for _, id := range d.idsByState("paused", "error", "canceled") {
		_ = d.Resume(id)
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

func (d *DownloadService) isRunnable(t downloadTask) (downloadTask, bool) {
	d.mu.Lock()
	defer d.mu.Unlock()
	stored, exists := d.tasks[t.id]
	if d.closed || !exists || d.attempts[t.id] != t.attempt || d.states[t.id] != "queued" || d.canceled[t.id] {
		return downloadTask{}, false
	}
	return stored, true
}

func (d *DownloadService) acquireRunLock(taskID string) *taskRunLock {
	d.mu.Lock()
	lock := d.runLocks[taskID]
	if lock == nil {
		lock = &taskRunLock{}
		d.runLocks[taskID] = lock
	}
	lock.refs++
	d.mu.Unlock()
	lock.mu.Lock()
	return lock
}

func (d *DownloadService) releaseRunLock(taskID string, lock *taskRunLock) {
	lock.mu.Unlock()
	d.mu.Lock()
	lock.refs--
	if lock.refs == 0 && d.runLocks[taskID] == lock {
		delete(d.runLocks, taskID)
	}
	d.mu.Unlock()
}

func (d *DownloadService) worker() {
	for {
		select {
		case <-d.workerCtx.Done():
			return
		case t := <-d.queue:
			d.runQueued(t)
		}
	}
}

func (d *DownloadService) runQueued(t downloadTask) {
	lock := d.acquireRunLock(t.id)
	defer d.releaseRunLock(t.id, lock)

	stored, ok := d.isRunnable(t)
	if ok {
		d.run(stored)
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
	ctx, cancel := context.WithCancel(d.workerCtx)
	d.mu.Lock()
	_, exists := d.tasks[t.id]
	if d.closed || !exists || d.attempts[t.id] != t.attempt || d.states[t.id] != "queued" || d.canceled[t.id] {
		d.mu.Unlock()
		cancel()
		return
	}
	d.cancels[t.id] = cancel
	d.cancelAttempts[t.id] = t.attempt
	d.mu.Unlock()
	defer func() {
		cancel()
		d.mu.Lock()
		if d.cancelAttempts[t.id] == t.attempt {
			delete(d.cancels, t.id)
			delete(d.cancelAttempts, t.id)
		}
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
			} else if pct < 0 {
				pct = 0
			}
			if p.Filename != "" {
				fm.Lock()
				lastFile = p.Filename
				fm.Unlock()
			}
			d.emitAttempt(TaskProgress{
				TaskID: t.id, State: "downloading", Percent: pct,
				Speed: p.Speed, ETA: p.ETA, BatchID: t.batchID, BatchTitle: t.batchTitle,
			}, t.attempt)
			d.touchBatch(t.id, pct, t.attempt)
		},
		OnPostprocess: func(name string) {
			d.emitAttempt(TaskProgress{TaskID: t.id, State: "converting", Percent: 100, BatchID: t.batchID, BatchTitle: t.batchTitle}, t.attempt)
			d.log(t.id, "postprocess: "+name)
		},
		OnFile: func(p string) {
			fm.Lock()
			lastFile = p
			fm.Unlock()
		},
		OnLog: func(line string) { d.log(t.id, line) },
	}

	if err := d.emitAttempt(TaskProgress{TaskID: t.id, State: "downloading", BatchID: t.batchID, BatchTitle: t.batchTitle}, t.attempt); !err {
		return
	}
	toolRelease, gateErr := acquireToolRead(ctx)
	var err error
	if gateErr != nil {
		err = gateErr
	} else {
		func() {
			defer toolRelease()
			args := engine.BuildArgs(t.opts, t.entry, t.pl)
			err = engine.RunDownload(ctx, args, taskURL(t.entry), hooks)
		}()
	}

	d.mu.Lock()
	if _, exists := d.tasks[t.id]; !exists || d.attempts[t.id] != t.attempt {
		d.mu.Unlock()
		return
	}
	wasCanceled := d.canceled[t.id]
	wasPaused := d.paused[t.id]
	d.mu.Unlock()

	fm.Lock()
	lf := lastFile
	fm.Unlock()

	switch {
	case wasPaused:
		if d.finish(t.id, t.attempt, "paused", "", "") {
			d.syncBatch(t.batchID)
		}
	case wasCanceled || ctx.Err() != nil:
		if d.finish(t.id, t.attempt, "canceled", "", "") {
			d.syncBatch(t.batchID)
		}
	case err != nil:
		if d.finish(t.id, t.attempt, "error", err.Error(), "") {
			d.syncBatch(t.batchID)
		}
	default:
		if d.finish(t.id, t.attempt, "done", "", d.finalPath(t, lf)) {
			d.syncBatch(t.batchID)
		}
	}
}

func isTerminalTaskState(state string) bool {
	switch state {
	case "done", "error", "canceled", "paused":
		return true
	default:
		return false
	}
}

// setStateLocked updates the task and its batch projection while d.mu is held.
func (d *DownloadService) setStateLocked(p TaskProgress) {
	d.states[p.TaskID] = p.State
	if b := d.batches[d.taskBatch[p.TaskID]]; b != nil {
		switch p.State {
		case "done", "error", "canceled":
			b.states[p.TaskID] = p.State
			if p.State == "done" {
				b.percent[p.TaskID] = 100
			}
		default:
			delete(b.states, p.TaskID)
		}
	}
}

func publishTaskProgress(p TaskProgress) {
	if app := application.Get(); app != nil {
		app.Event.Emit("task:progress", p)
	}
}

func (d *DownloadService) finish(taskID string, attempt uint64, state, errMsg, filePath string) bool {
	d.mu.Lock()
	t, ok := d.tasks[taskID]
	currentState := d.states[taskID]
	allowedCancelFromPaused := currentState == "paused" && state == "canceled"
	if !ok || d.attempts[taskID] != attempt || (isTerminalTaskState(currentState) && !allowedCancelFromPaused) {
		d.mu.Unlock()
		return false
	}
	// Cancel/Pause may arrive after run() has inspected ctx.Err() but before
	// it commits the final result. Do not let that stale result override the
	// user's action.
	if d.canceled[taskID] && (state == "done" || state == "error") {
		d.mu.Unlock()
		return false
	}
	pct := d.percents[taskID]
	if state == "done" {
		pct = 100
		d.percents[taskID] = 100
		d.files[taskID] = filePath
	}
	if state == "error" {
		d.errors[taskID] = errMsg
	} else {
		delete(d.errors, taskID)
	}
	p := TaskProgress{
		TaskID: taskID, State: state, Percent: pct, Error: errMsg, FilePath: filePath,
		BatchID: t.batchID, BatchTitle: t.batchTitle,
	}
	d.setStateLocked(p)
	d.mu.Unlock()
	d.persistQueueQuiet()
	publishTaskProgress(p)
	return true
}

func (d *DownloadService) touchBatch(taskID string, pct float64, attempt uint64) {
	d.mu.Lock()
	if _, ok := d.tasks[taskID]; !ok || d.attempts[taskID] != attempt {
		d.mu.Unlock()
		return
	}
	if state := d.states[taskID]; (state != "downloading" && state != "converting") || d.canceled[taskID] {
		d.mu.Unlock()
		return
	}
	d.percents[taskID] = pct
	bid := d.taskBatch[taskID]
	var snap *BatchProgress
	persistNow := false
	if b := d.batches[bid]; b != nil {
		b.percent[taskID] = pct
		if time.Since(b.lastEmit) >= 400*time.Millisecond {
			b.lastEmit = time.Now()
			s := b.snapshot(bid)
			snap = &s
		}
	}
	if time.Since(d.lastPersistAt) >= 3*time.Second {
		d.lastPersistAt = time.Now()
		persistNow = true
	}
	d.mu.Unlock()
	if persistNow {
		d.persistQueueQuiet()
	}
	if snap != nil {
		d.emitBatch(*snap)
	}
}

func (d *DownloadService) syncBatch(batchID string) {
	if batchID == "" {
		return
	}
	d.mu.Lock()
	var snap *BatchProgress
	if b := d.batches[batchID]; b != nil {
		s := b.snapshot(batchID)
		snap = &s
	}
	d.mu.Unlock()
	if snap == nil {
		return
	}
	d.emitBatch(*snap)
	if snap.Done {
		if app := application.Get(); app != nil {
			app.Event.Emit("batch:completed", *snap)
		}
	}
}

func (d *DownloadService) emitAttempt(p TaskProgress, attempt uint64) bool {
	d.mu.Lock()
	if _, ok := d.tasks[p.TaskID]; !ok || d.attempts[p.TaskID] != attempt {
		d.mu.Unlock()
		return false
	}
	if p.State == "downloading" || p.State == "converting" {
		if d.closed || d.canceled[p.TaskID] || d.paused[p.TaskID] || isTerminalTaskState(d.states[p.TaskID]) {
			d.mu.Unlock()
			return false
		}
	}
	changed := d.states[p.TaskID] != p.State
	d.setStateLocked(p)
	d.mu.Unlock()
	if changed {
		d.persistQueueQuiet()
	}
	publishTaskProgress(p)
	return true
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

func batchNumber(id string) int {
	var n int
	_, _ = fmt.Sscanf(id, "batch-%d", &n)
	return n
}

func (d *DownloadService) deleteTaskLocked(id string) {
	delete(d.tasks, id)
	delete(d.queueOrder, id)
	delete(d.states, id)
	delete(d.canceled, id)
	delete(d.paused, id)
	delete(d.cancels, id)
	delete(d.percents, id)
	delete(d.files, id)
	delete(d.errors, id)
	delete(d.taskBatch, id)
	delete(d.attempts, id)
	delete(d.cancelAttempts, id)
}

func (d *DownloadService) restoreQueue(snapshot queueSnapshot) {
	d.seq, d.batchSeq, d.queueSequence = snapshot.Sequence, snapshot.BatchSequence, snapshot.QueueSequence
	for _, pb := range snapshot.Batches {
		d.batches[pb.ID] = &batchState{title: pb.Title, kind: pb.Kind, total: pb.Total,
			ids: append([]string(nil), pb.IDs...), states: map[string]string{},
			percent: map[string]float64{}}
		for id, pct := range pb.Percent {
			d.batches[pb.ID].percent[id] = pct
		}
	}
	var queued []downloadTask
	for _, pt := range snapshot.Tasks {
		if strings.TrimSpace(pt.ID) == "" || pt.Attempt == 0 {
			continue
		}
		t := downloadTask{id: pt.ID, batchID: pt.BatchID, batchTitle: pt.BatchTitle,
			title: pt.Title, attempt: pt.Attempt, entry: pt.Entry, opts: pt.Options, pl: pt.Playlist}
		state := pt.State
		switch state {
		case "queued", "downloading", "converting", "paused", "done", "error", "canceled":
		default:
			state = "error"
		}
		if state != "done" {
			if validationErr := validateQueuedTask(t); validationErr != nil {
				state = "error"
				pt.Error = validationErr.Error()
			}
		}
		if state == "downloading" || state == "converting" {
			state = "paused"
			pt.Error = "Uygulama önceki oturumda kapandı; indirmeyi sürdürmek için Sürdür'e basın."
		}
		d.tasks[t.id] = t
		d.attempts[t.id] = t.attempt
		d.states[t.id] = state
		d.percents[t.id] = pt.Percent
		d.files[t.id] = pt.FilePath
		d.errors[t.id] = pt.Error
		d.taskBatch[t.id] = t.batchID
		order := pt.QueueOrder
		if order == 0 {
			d.queueSequence++
			order = d.queueSequence
		}
		d.queueOrder[t.id] = order
		if order > d.queueSequence {
			d.queueSequence = order
		}
		if state == "paused" {
			d.paused[t.id] = true
		}
		if b := d.batches[t.batchID]; b != nil {
			if !containsString(b.ids, t.id) {
				b.ids = append(b.ids, t.id)
			}
			b.percent[t.id] = pt.Percent
			switch state {
			case "done", "error", "canceled":
				b.states[t.id] = state
			}
		} else if t.batchID != "" {
			b := &batchState{title: t.batchTitle, kind: "file", total: 1,
				ids: []string{t.id}, states: map[string]string{}, percent: map[string]float64{t.id: pt.Percent}}
			if state == "done" || state == "error" || state == "canceled" {
				b.states[t.id] = state
			}
			d.batches[t.batchID] = b
		}
		if n := taskSequence(t.id); n > d.seq {
			d.seq = n
		}
		if state == "queued" {
			queued = append(queued, t)
		}
	}
	for _, b := range d.batches {
		if b.total < len(b.ids) {
			b.total = len(b.ids)
		}
	}
	sort.Slice(queued, func(i, j int) bool { return d.queueOrder[queued[i].id] < d.queueOrder[queued[j].id] })
	for _, t := range queued {
		d.queue <- t
	}
}

func containsString(items []string, value string) bool {
	for _, item := range items {
		if item == value {
			return true
		}
	}
	return false
}

func taskSequence(id string) int {
	var n int
	if i := strings.LastIndex(id, "-"); i >= 0 {
		_, _ = fmt.Sscanf(id[i+1:], "%d", &n)
	}
	return n
}

func (d *DownloadService) persistQueue() error {
	if d.store == nil {
		return nil
	}
	d.persistMu.Lock()
	defer d.persistMu.Unlock()
	d.mu.Lock()
	snapshot := queueSnapshot{Version: queueStoreVersion, Sequence: d.seq,
		BatchSequence: d.batchSeq, QueueSequence: d.queueSequence}
	ids := make([]string, 0, len(d.tasks))
	for id := range d.tasks {
		ids = append(ids, id)
	}
	sort.Slice(ids, func(i, j int) bool { return d.queueOrder[ids[i]] < d.queueOrder[ids[j]] })
	for _, id := range ids {
		t := d.tasks[id]
		snapshot.Tasks = append(snapshot.Tasks, persistedTask{ID: id, BatchID: t.batchID,
			BatchTitle: t.batchTitle, Title: t.title, Attempt: d.attempts[id], Entry: t.entry,
			Options: t.opts, Playlist: t.pl, State: d.states[id], Percent: d.percents[id],
			FilePath: d.files[id], Error: d.errors[id], QueueOrder: d.queueOrder[id]})
	}
	batchIDs := make([]string, 0, len(d.batches))
	for id := range d.batches {
		batchIDs = append(batchIDs, id)
	}
	sort.Slice(batchIDs, func(i, j int) bool { return batchNumber(batchIDs[i]) < batchNumber(batchIDs[j]) })
	for _, id := range batchIDs {
		b := d.batches[id]
		percent := make(map[string]float64, len(b.percent))
		for taskID, pct := range b.percent {
			percent[taskID] = pct
		}
		snapshot.Batches = append(snapshot.Batches, persistedBatch{ID: id, Title: b.title,
			Kind: b.kind, Total: b.total, IDs: append([]string(nil), b.ids...), Percent: percent})
	}
	d.mu.Unlock()
	return d.store.Save(snapshot)
}

func (d *DownloadService) persistQueueQuiet() {
	if err := d.persistQueue(); err != nil {
		log.Printf("download queue persistence failed: %v", err)
	}
}

// Shutdown stops accepting work, persists queued items and marks active items
// paused before terminating yt-dlp/FFmpeg process groups.
func (d *DownloadService) shutdown(ctx context.Context) error {
	var persistErr error
	d.shutdownOnce.Do(func() {
		d.mu.Lock()
		d.closed = true
		cancels := make([]context.CancelFunc, 0, len(d.cancels))
		for id, state := range d.states {
			if state == "downloading" || state == "converting" {
				d.paused[id] = true
				d.canceled[id] = true
				d.states[id] = "paused"
				if b := d.batches[d.taskBatch[id]]; b != nil {
					delete(b.states, id)
				}
			}
			if cancel := d.cancels[id]; cancel != nil {
				cancels = append(cancels, cancel)
			}
		}
		d.mu.Unlock()
		persistErr = d.persistQueue()
		for _, cancel := range cancels {
			cancel()
		}
		d.workerCancel()
	})
	done := make(chan struct{})
	go func() { d.workerWG.Wait(); close(done) }()
	select {
	case <-done:
		return persistErr
	case <-ctx.Done():
		if persistErr != nil {
			return errors.Join(persistErr, ctx.Err())
		}
		return ctx.Err()
	}
}
