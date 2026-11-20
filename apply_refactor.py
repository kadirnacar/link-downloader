#!/usr/bin/env python3
"""
apply_round3.py — Round 3
  - services/download.go: downloadTask.batchTitle field eklendi
    (TaskProgress.BatchTitle artık batch başlığını taşır, task başlığını değil)
  - services/download_test.go: YENİ — queue/batch unit testleri

Ön koşul: apply_refactor.py + apply_round2.py çalışmış olmalı.
Idempotent. Backup YOK.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
CHANGES = []


def report(status, path, message):
    CHANGES.append((status, str(path.relative_to(ROOT)), message))
    icon = {"OK": "✓", "SKIP": "○", "FAIL": "✗"}.get(status, "?")
    print(f"  {icon} {status:4} {path.relative_to(ROOT)} — {message}")


def read(path):
    if not path.exists():
        raise FileNotFoundError(f"Yok: {path}")
    return path.read_text(encoding="utf-8")


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def patch_exact(path, old, new, description, skip_if_present=None):
    content = read(path)
    if skip_if_present and skip_if_present in content:
        report("SKIP", path, f"zaten uygulanmış ({description})")
        return False
    n = content.count(old)
    if n == 0:
        raise RuntimeError(f"Beklenen içerik yok: {path}\n  Açıklama: {description}\n"
                           f"  Aranan:\n{old[:200]}")
    if n > 1:
        raise RuntimeError(f"Belirsiz ({n} eşleşme): {path}\n  Açıklama: {description}")
    new_content = content.replace(old, new, 1)
    if new not in new_content:
        raise RuntimeError(f"Post-patch doğrulama başarısız: {path}")
    write(path, new_content)
    report("OK", path, description)
    return True


# ============================================================
# services/download.go — downloadTask.batchTitle + 6 fix
# ============================================================
def fix_download_go():
    path = ROOT / "services" / "download.go"

    # 1) Struct'a batchTitle ekle
    old_struct = (
        "type downloadTask struct {\n"
        "\tid      string\n"
        "\tbatchID string\n"
        "\ttitle   string\n"
        "\tentry   model.MediaEntry\n"
        "\topts    model.DownloadOptions\n"
        "\tpl      engine.PlaylistContext\n"
        "}"
    )
    new_struct = (
        "type downloadTask struct {\n"
        "\tid         string\n"
        "\tbatchID    string\n"
        "\tbatchTitle string\n"
        "\ttitle      string\n"
        "\tentry      model.MediaEntry\n"
        "\topts       model.DownloadOptions\n"
        "\tpl         engine.PlaylistContext\n"
        "}"
    )
    patch_exact(path, old_struct, new_struct,
                "downloadTask.batchTitle alanı eklendi")

    # 2) Enqueue'da batchTitle ata
    old_enq = '\t\tt := downloadTask{id: id, batchID: bid, title: e.Title, opts: opts, pl: pl}'
    new_enq = '\t\tt := downloadTask{id: id, batchID: bid, batchTitle: title, title: e.Title, opts: opts, pl: pl}'
    patch_exact(path, old_enq, new_enq,
                "Enqueue: batchTitle atandı")

    # 3) Resume
    patch_exact(path,
        '\td.emit(TaskProgress{TaskID: taskID, State: "queued", BatchID: bid, BatchTitle: t.title})',
        '\td.emit(TaskProgress{TaskID: taskID, State: "queued", BatchID: bid, BatchTitle: t.batchTitle})',
        "Resume: BatchTitle düzeltildi")

    # 4) run() başlangıç
    patch_exact(path,
        '\td.emit(TaskProgress{TaskID: t.id, State: "downloading", BatchID: t.batchID, BatchTitle: t.title})',
        '\td.emit(TaskProgress{TaskID: t.id, State: "downloading", BatchID: t.batchID, BatchTitle: t.batchTitle})',
        "run() ilk emit: BatchTitle düzeltildi")

    # 5) run() OnProgress
    patch_exact(path,
        "\t\t\td.emit(TaskProgress{\n"
        "\t\t\t\tTaskID: t.id, State: \"downloading\", Percent: pct,\n"
        "\t\t\t\tSpeed: p.Speed, ETA: p.ETA, BatchID: t.batchID, BatchTitle: t.title,\n"
        "\t\t\t})",
        "\t\t\td.emit(TaskProgress{\n"
        "\t\t\t\tTaskID: t.id, State: \"downloading\", Percent: pct,\n"
        "\t\t\t\tSpeed: p.Speed, ETA: p.ETA, BatchID: t.batchID, BatchTitle: t.batchTitle,\n"
        "\t\t\t})",
        "run() OnProgress: BatchTitle düzeltildi")

    # 6) run() OnPostprocess
    patch_exact(path,
        '\t\t\td.emit(TaskProgress{TaskID: t.id, State: "converting", Percent: 100, BatchID: t.batchID, BatchTitle: t.title})',
        '\t\t\td.emit(TaskProgress{TaskID: t.id, State: "converting", Percent: 100, BatchID: t.batchID, BatchTitle: t.batchTitle})',
        "run() OnPostprocess: BatchTitle düzeltildi")

    # 7) finish()
    patch_exact(path,
        "\td.emit(TaskProgress{\n"
        "\t\tTaskID: taskID, State: state, Percent: pct, Error: errMsg, FilePath: filePath,\n"
        "\t\tBatchID: t.batchID, BatchTitle: t.title,\n"
        "\t})",
        "\td.emit(TaskProgress{\n"
        "\t\tTaskID: taskID, State: state, Percent: pct, Error: errMsg, FilePath: filePath,\n"
        "\t\tBatchID: t.batchID, BatchTitle: t.batchTitle,\n"
        "\t})",
        "finish(): BatchTitle düzeltildi")

    # 8) Snapshot()
    patch_exact(path,
        "\t\tout = append(out, TaskProgress{\n"
        "\t\t\tTaskID: id, State: st, Percent: d.percents[id],\n"
        "\t\t\tError: d.errors[id], FilePath: d.files[id],\n"
        "\t\t\tBatchID: t.batchID, BatchTitle: t.title,\n"
        "\t\t})",
        "\t\tout = append(out, TaskProgress{\n"
        "\t\t\tTaskID: id, State: st, Percent: d.percents[id],\n"
        "\t\t\tError: d.errors[id], FilePath: d.files[id],\n"
        "\t\t\tBatchID: t.batchID, BatchTitle: t.batchTitle,\n"
        "\t\t})",
        "Snapshot(): BatchTitle düzeltildi")


# ============================================================
# services/download_test.go — YENİ
# ============================================================
TEST_FILE = r'''// ytdlp-studio:download-test v1
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
'''


def create_test_file():
    path = ROOT / "services" / "download_test.go"
    if path.exists():
        report("SKIP", path, "zaten var")
        return
    write(path, TEST_FILE)
    report("OK", path, "yeni test dosyası oluşturuldu (7 test)")


# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 62)
    print("apply_round3.py")
    print("=" * 62)

    if not (ROOT / "services" / "download.go").exists():
        print(f"✗ services/download.go yok. Kök: {ROOT}")
        sys.exit(1)
    print(f"✓ Proje kökü: {ROOT}")

    steps = [
        ("services/download.go — BatchTitle fix", fix_download_go),
        ("services/download_test.go — yeni testler", create_test_file),
    ]
    failed = []
    for label, fn in steps:
        print(f"\n▶ {label}")
        try:
            fn()
        except Exception as e:
            print(f"  ✗ FAIL: {e}")
            failed.append((label, str(e)))

    print("\n" + "=" * 62)
    print("ÖZET")
    print("=" * 62)
    for status, path, msg in CHANGES:
        icon = {"OK": "✓", "SKIP": "○", "FAIL": "✗"}.get(status, "?")
        print(f"  {icon} {status:4} {path} — {msg}")

    if failed:
        print(f"\n{len(failed)} adım başarısız.")
        sys.exit(1)

    print(f"\n✓ Round 3 tamamlandı ({len(CHANGES)} adım).")


if __name__ == "__main__":
    main()