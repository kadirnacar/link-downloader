// ytdlp-studio:generated v1
// ytdlp-studio:app v1
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
    const offDeps = Events.On("deps:status", (ev) => set({ deps: ev.data as DepStatus }));
    return () => {
      offProgress();
      offBatch();
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
  const pageTitle = tab === "analyze" ? "İçerik analizi" : "İndirme kuyruğu";

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">⬇</div>
          <div>
            <strong>ytdlp-studio</strong>
            <span>v3 · blend UI</span>
          </div>
        </div>
        <div style={{ width: "100%" }}>
          <div className="nav-label">Sekmeler</div>
          <nav className="nav">
            <button
              className={tab === "analyze" ? "active" : ""}
              onClick={() => set({ tab: "analyze" })}
            >
              <span className="ico">◈</span>
              Analiz
            </button>
            <button
              className={tab === "queue" ? "active" : ""}
              onClick={() => set({ tab: "queue" })}
            >
              <span className="ico">▤</span>
              Kuyruk
            </button>
          </nav>
        </div>
        <div className="sidebar-bottom">
          <strong>Yerel araçlar</strong>
          yt-dlp, ffmpeg ve ffprobe otomatik yönetilir. Eksikse üstteki banner'dan kurabilirsiniz.
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <div className="eyebrow">ytdlp-studio</div>
            <h1>{pageTitle}</h1>
          </div>
          <div className="conn-box">
            <button className="btn ghost" onClick={() => void updateYtDlp()}>
              yt-dlp Güncelle
            </button>
          </div>
        </header>

        {missing.length > 0 && (
          <div className="banner">
            <span>Eksik bileşenler: {missing.join(", ")}</span>
            <button className="btn danger" onClick={() => void installDeps()} disabled={installing}>
              {installing ? "Kuruluyor…" : "Otomatik Kur"}
            </button>
          </div>
        )}

        {notice && (
          <div
            className={"notice" + (notice.toLowerCase().includes("başarısız") || notice.toLowerCase().includes("hata") ? " error" : "")}
            onClick={() => set({ notice: undefined })}
          >
            {notice}
          </div>
        )}

        {tab === "analyze" ? (
          <>
            <PasteBar />
            <div className="grid two">
              <PreviewList />
              <OptionsPanel />
            </div>
            <footer className="actionbar">
              <DownloadButton />
            </footer>
          </>
        ) : (
          <QueuePanel />
        )}
      </main>
      <Toasts />
    </div>
  );
}
