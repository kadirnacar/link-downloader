#!/usr/bin/env python3
"""
ytdlp-studio · addMany imza düzeltmesi + tam ekran layout

1. frontend/src/taskStore.ts → addMany 3. opsiyonel parametre (batchId) kabul eder
2. frontend/src/index.css    → tam pencere layout kuralları (idempotent append)

Backup oluşturmaz. Markdown üretmez.
"""

import subprocess
import sys
from pathlib import Path

ROOT = None
MODIFIED = []
CREATED = []


def find_project_root():
    current = Path.cwd()
    while current != current.parent:
        if (current / "go.mod").exists() and (current / "Taskfile.yml").exists():
            return current
        current = current.parent
    fail("Proje kökü bulunamadı (go.mod + Taskfile.yml aranıyor).")


def rel(p):
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def fail(msg):
    print("\nERROR:")
    print(msg)
    print("\nPatch uygulanmadı.")
    sys.exit(1)


def read(p):
    if not p.exists():
        fail(f"Dosya bulunamadı:\n{p}")
    return p.read_text(encoding="utf-8")


def write(p, content):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def run(cmd, cwd=None, ok_fail=False):
    print("$ " + " ".join(str(c) for c in cmd))
    proc = subprocess.run([str(c) for c in cmd], cwd=str(cwd) if cwd else None,
                          text=True, capture_output=True)
    if proc.stdout:
        print(proc.stdout.rstrip()[:4000])
    if proc.stderr:
        print(proc.stderr.rstrip()[:4000])
    if proc.returncode != 0 and not ok_fail:
        return False
    return True


# --------------------------------------------------------------------------- #
# 1. taskStore.ts — addMany 3. parametre kabul etsin
# --------------------------------------------------------------------------- #
TASK_STORE_FULL = '''// ytdlp-studio:generated v1
// ytdlp-studio:taskstore v3
import { create } from "zustand";
import type { MediaEntry, TaskProgress } from "./types";

export interface TaskItem extends TaskProgress {
  title: string;
}

interface TaskState {
  tasks: Record<string, TaskItem>;
  order: string[];
  addMany: (ids: string[], entries: MediaEntry[], batchId?: string) => void;
  upsert: (p: TaskProgress) => void;
  removeOne: (id: string) => void;
  clearFinished: () => void;
  clearAll: () => void;
}

export const useTasks = create<TaskState>((set) => ({
  tasks: {},
  order: [],
  addMany: (ids, entries, batchId) =>
    set((s) => {
      const tasks = { ...s.tasks };
      const order = [...s.order];
      ids.forEach((id, i) => {
        const e = entries[i];
        tasks[id] = {
          taskId: id,
          title: e ? e.title : id,
          state: "queued",
          percent: 0,
          speedBps: 0,
          etaSec: 0,
          batchId: batchId || undefined,
        };
        order.push(id);
      });
      return { tasks, order };
    }),
  upsert: (p) =>
    set((s) => {
      const prev = s.tasks[p.taskId];
      const base: TaskItem =
        prev ??
        { taskId: p.taskId, title: "", state: "queued", percent: 0, speedBps: 0, etaSec: 0 };
      const item: TaskItem = {
        ...base,
        ...p,
        batchId: p.batchId || base.batchId,
        error: p.state === "error" ? p.error : undefined,
      };
      const order = prev ? s.order : [...s.order, p.taskId];
      return { tasks: { ...s.tasks, [p.taskId]: item }, order };
    }),
  removeOne: (id) =>
    set((s) => {
      const tasks = { ...s.tasks };
      delete tasks[id];
      return { tasks, order: s.order.filter((x) => x !== id) };
    }),
  clearFinished: () =>
    set((s) => {
      const order = s.order.filter((id) => {
        const t = s.tasks[id];
        return t && t.state !== "done" && t.state !== "canceled";
      });
      const tasks: Record<string, TaskItem> = {};
      order.forEach((id) => {
        const t = s.tasks[id];
        if (t) tasks[id] = t;
      });
      return { tasks, order };
    }),
  clearAll: () => set({ tasks: {}, order: [] }),
}));
'''


def patch_task_store():
    path = ROOT / "frontend" / "src" / "taskStore.ts"
    write(path, TASK_STORE_FULL)
    MODIFIED.append("frontend/src/taskStore.ts (addMany batchId parametresi)")
    print("UPDATED : frontend/src/taskStore.ts")


# --------------------------------------------------------------------------- #
# 2. types.ts — batchId alanını TaskProgress'e ekle (eksikse)
# --------------------------------------------------------------------------- #
TYPES_FULL = '''// ytdlp-studio:generated v1
// ytdlp-studio:types v3

export interface ParsedURL {
  kind: string;
  videoId: string;
  listId: string;
  canonicalUrl: string;
  ambiguous: boolean;
  isMix: boolean;
}

export interface MediaEntry {
  id: string;
  url: string;
  title: string;
  durationSec: number;
  thumbnail: string;
  index: number;
  available: boolean;
}

export interface MediaInfo {
  kind: string;
  id: string;
  title: string;
  entries: MediaEntry[] | null;
}

export interface DownloadOptions {
  mode: string;
  audioFormat: string;
  audioQuality: string;
  videoHeight: number;
  videoContainer: string;
  outputDir: string;
  nameTemplate: string;
  embedThumbnail: boolean;
  embedMetadata: boolean;
  concurrentFragments: number;
  rateLimit: string;
  cookiesBrowser: string;
}

export interface TaskProgress {
  taskId: string;
  state: string;
  percent: number;
  speedBps: number;
  etaSec: number;
  error?: string;
  filePath?: string;
  batchId?: string;
}

export interface BatchProgress {
  batchId: string;
  total: number;
  completed: number;
  failed: number;
  current: number;
  done: boolean;
}

export interface DepStatus {
  ytDlp: boolean;
  ffmpeg: boolean;
  ffprobe: boolean;
  jsRuntime: string;
  missing: string[] | null;
}
'''


def patch_types():
    path = ROOT / "frontend" / "src" / "types.ts"
    write(path, TYPES_FULL)
    MODIFIED.append("frontend/src/types.ts (batchId + BatchProgress)")
    print("UPDATED : frontend/src/types.ts")


# --------------------------------------------------------------------------- #
# 3. index.css — tam pencere layout (idempotent append)
# --------------------------------------------------------------------------- #
LAYOUT_CSS_MARKER = "/* ytdlp-studio:fullscreen-layout v1 */"
LAYOUT_CSS = '''
/* ytdlp-studio:fullscreen-layout v1 */
html, body, #root {
  margin: 0;
  padding: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  box-sizing: border-box;
}

*, *::before, *::after {
  box-sizing: border-box;
}

.app {
  width: 100%;
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.topbar {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.analyze, .queue {
  flex: 1 1 auto;
  overflow-y: auto;
  overflow-x: hidden;
  min-height: 0;
  padding: 16px 20px;
}

.analyze-grid {
  display: grid;
  grid-template-columns: 1fr 320px;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

.pastebar {
  display: flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.pastebar-field {
  flex: 1 1 auto;
  min-width: 200px;
  display: flex;
}

.pastebar-field .url-input {
  flex: 1 1 auto;
  min-width: 0;
  width: 100%;
}

.pastebar-side {
  display: flex;
  gap: 8px;
  align-items: center;
  flex: 0 0 auto;
}

.pastebar-btn {
  min-width: 138px;
  flex: 0 0 auto;
  white-space: nowrap;
}

.pastebar-scope {
  flex: 0 0 auto;
  width: 150px;
}

.pastebar .chip,
.pastebar .warn {
  flex: 0 0 auto;
  white-space: nowrap;
}

.pastebar-error {
  flex: 1 1 100%;
}

.actionbar {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.preview {
  overflow-y: auto;
  min-height: 0;
}

.queue-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.queue-panel .rows {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.task-btns {
  display: inline-flex;
  gap: 6px;
  flex: 0 0 auto;
  white-space: nowrap;
}

.task-btns button {
  white-space: nowrap;
}

.queue-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}

.queue-actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.queue-actions button {
  white-space: nowrap;
}

.batch-card {
  padding: 10px 12px;
  margin: 8px 0;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
}

.batch-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
  font-size: 13px;
}

.batch-head .muted {
  opacity: 0.7;
}

.toast-wrap {
  position: fixed;
  right: 18px;
  bottom: 18px;
  z-index: 99;
  display: grid;
  gap: 8px;
  width: min(370px, calc(100vw - 36px));
}

.toast {
  padding: 12px 14px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(20, 24, 32, 0.96);
  border-radius: 10px;
  font-size: 13px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
}

.toast.good {
  border-color: rgba(90, 200, 130, 0.5);
}

.toast.bad {
  border-color: rgba(240, 110, 120, 0.5);
}
/* ytdlp-studio:fullscreen-layout v1:end */
'''


def patch_css():
    path = ROOT / "frontend" / "src" / "index.css"
    if not path.exists():
        # index.css yoksa oluştur
        write(path, LAYOUT_CSS.strip() + "\n")
        CREATED.append("frontend/src/index.css (fullscreen layout)")
        print("CREATED : frontend/src/index.css")
        return

    content = read(path)
    end_marker = "/* ytdlp-studio:fullscreen-layout v1:end */"

    if LAYOUT_CSS_MARKER in content and end_marker in content:
        # Blok zaten var, değiştir
        start = content.index(LAYOUT_CSS_MARKER)
        end = content.index(end_marker) + len(end_marker)
        content = content[:start] + LAYOUT_CSS.strip() + content[end:]
        MODIFIED.append("frontend/src/index.css (fullscreen layout bloğu güncellendi)")
        print("UPDATED : frontend/src/index.css (layout block replaced)")
    else:
        # Blok yok, sona ekle
        content = content.rstrip() + "\n\n" + LAYOUT_CSS.strip() + "\n"
        MODIFIED.append("frontend/src/index.css (fullscreen layout bloğu eklendi)")
        print("UPDATED : frontend/src/index.css (layout block appended)")

    write(path, content)

    if LAYOUT_CSS_MARKER not in read(path):
        fail("CSS layout bloğu doğrulanamadı.")


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main():
    global ROOT
    ROOT = find_project_root()
    print(f"Project root: {ROOT}\n")

    print("=== Frontend düzeltmeleri ===")
    patch_types()
    patch_task_store()
    patch_css()

    print("\n=== Doğrulama ===")
    frontend = ROOT / "frontend"
    if not run(["npm", "run", "build:dev"], cwd=frontend):
        fail("frontend build başarısız")

    print("\n=== UPDATE SUMMARY ===")
    print("\nModified:")
    for m in MODIFIED:
        print(f"  - {m}")
    print("\nCreated:")
    for c in CREATED:
        print(f"  - {c}")
    if not CREATED:
        print("  - (yok)")
    print("\nValidation:")
    print("  - frontend build:dev: PASS")
    print("\nCompleted successfully.")

    print("\n=== GIT COMMIT MESSAGE ===")
    print(
        "fix(ui): resolve addMany signature mismatch and add fullscreen layout\n"
        "\n"
        "- Update taskStore.ts addMany to accept optional batchId parameter\n"
        "- Add batchId field to TaskProgress type\n"
        "- Add fullscreen layout CSS rules (100vh, flex column, overflow)\n"
        "- Ensure analyze/queue panels fill available window space\n"
        "- Fix PasteBar input shrinking with flex-wrap and min-width\n"
    )


if __name__ == "__main__":
    main()