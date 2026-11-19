// ytdlp-studio:generated v1
// ytdlp-studio:app v2
import { useEffect } from "react";
import { Events } from "@wailsio/runtime";
import { DepsService, SettingsService } from "./api";
import { useStore } from "./store";
import { useTasks } from "./taskStore";
import type { BatchProgress, DepStatus, TaskProgress } from "./types";
import { PasteBar } from "./components/PasteBar";
import { PreviewList } from "./components/PreviewList";
import { OptionsPanel } from "./components/OptionsPanel";
import { DownloadButton } from "./components/DownloadButton";
import { QueuePanel } from "./components/QueuePanel";
import { Toasts } from "./components/Toasts";

export default function App() {
  const tab = useStore((s) => s.tab);
  const deps = useStore((s) => s.deps);
  const installing = useStore((s) => s.installing);
  const notice = useStore((s) => s.notice);
  const set = useStore((s) => s.set);
  const upsertBatch = useStore((s) => s.upsertBatch);
  const upsert = useTasks((s) => s.upsert);

  useEffect(() => {
    const offProgress = Events.On("task:progress", (ev) => upsert(ev.data as TaskProgress));
    const offBatch = Events.On("batch:progress", (ev) => upsertBatch(ev.data as BatchProgress));
    const offBatchDone = Events.On("batch:completed", (ev) => upsertBatch(ev.data as BatchProgress));
    const offDeps = Events.On("deps:status", (ev) => set({ deps: ev.data as DepStatus }));
    return () => {
      offProgress();
      offBatch();
      offBatchDone();
      offDeps();
    };
  }, [upsert, upsertBatch, set]);

  useEffect(() => {
    SettingsService.Load()
      .then((o) => set({ options: o }))
      .catch(() => undefined);
    DepsService.CheckDeps()
      .then((d) => set({ deps: d }))
      .catch(() => undefined);
  }, [set]);

  async function installDeps() {
    set({ installing: true, notice: undefined });
    try {
      const d = await DepsService.InstallDeps();
      set({ deps: d, notice: "Bileşenler hazır." });
    } catch (e) {
      set({ notice: String(e) });
    } finally {
      set({ installing: false });
    }
  }

  async function updateYtDlp() {
    set({ notice: "yt-dlp güncelleniyor…" });
    try {
      const out = await DepsService.UpdateYtDlp();
      set({ notice: out.trim() || "Güncel." });
    } catch (e) {
      set({ notice: String(e) });
    }
  }

  const missing = deps?.missing ?? [];

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">ytdlp-studio</div>
        <nav className="tabs">
          <button className={tab === "analyze" ? "tab active" : "tab"} onClick={() => set({ tab: "analyze" })}>
            Analiz
          </button>
          <button className={tab === "queue" ? "tab active" : "tab"} onClick={() => set({ tab: "queue" })}>
            Kuyruk
          </button>
        </nav>
        <div className="topbar-actions">
          <button className="ghost" onClick={() => void updateYtDlp()}>
            yt-dlp Güncelle
          </button>
        </div>
      </header>

      {missing.length > 0 && (
        <div className="banner">
          <span>Eksik bileşenler: {missing.join(", ")}</span>
          <button onClick={() => void installDeps()} disabled={installing}>
            {installing ? "Kuruluyor…" : "Otomatik Kur"}
          </button>
        </div>
      )}

      {notice && (
        <div className="notice" onClick={() => set({ notice: undefined })}>
          {notice}
        </div>
      )}

      {tab === "analyze" ? (
        <main className="analyze">
          <PasteBar />
          <div className="analyze-grid">
            <PreviewList />
            <OptionsPanel />
          </div>
          <footer className="actionbar">
            <DownloadButton />
          </footer>
        </main>
      ) : (
        <main className="queue">
          <QueuePanel />
        </main>
      )}
      <Toasts />
    </div>
  );
}
