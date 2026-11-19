// ytdlp-studio:generated v1
// ytdlp-studio:app v3
import { useEffect } from "react";
import { Events } from "@wailsio/runtime";
import { DepsService, SettingsService } from "./api";
import { useStore } from "./store";
import { useTasks } from "./taskStore";
import { useLogs } from "./logStore";
import type { BatchProgress, DepStatus, LogLine, TaskProgress } from "./types";
import { Sidebar } from "./components/Sidebar";
import { PasteBar } from "./components/PasteBar";
import { PreviewList } from "./components/PreviewList";
import { OptionsPanel } from "./components/OptionsPanel";
import { SubtitlePicker } from "./components/SubtitlePicker";
import { DownloadButton } from "./components/DownloadButton";
import { QueuePanel } from "./components/QueuePanel";
import { SettingsPage } from "./pages/SettingsPage";
import { LogsPage } from "./pages/LogsPage";
import { AboutPage } from "./pages/AboutPage";
import { Toasts } from "./components/Toasts";

const TITLES: Record<string, string> = {
  analyze: "İçerik analizi", queue: "İndirme kuyruğu",
  settings: "Ayarlar", logs: "Günlük", about: "Hakkında",
};

export default function App() {
  const tab = useStore((s) => s.tab);
  const app = useStore((s) => s.app);
  const deps = useStore((s) => s.deps);
  const mode = useStore((s) => s.options.mode);
  const installing = useStore((s) => s.installing);
  const notice = useStore((s) => s.notice);
  const set = useStore((s) => s.set);
  const upsertBatch = useStore((s) => s.upsertBatch);
  const upsert = useTasks((s) => s.upsert);
  const pushLog = useLogs((s) => s.push);
  const setLogLimit = useLogs((s) => s.setLimit);

  useEffect(() => {
    const offs = [
      Events.On("task:progress", (ev) => upsert(ev.data as TaskProgress)),
      Events.On("batch:progress", (ev) => upsertBatch(ev.data as BatchProgress)),
      Events.On("batch:completed", (ev) => upsertBatch(ev.data as BatchProgress)),
      Events.On("deps:status", (ev) => set({ deps: ev.data as DepStatus })),
      Events.On("log:line", (ev) => pushLog(ev.data as LogLine)),
    ];
    return () => offs.forEach((off) => off());
  }, [upsert, upsertBatch, pushLog, set]);

  useEffect(() => {
    SettingsService.Load().then((o) => set({ options: o })).catch(() => undefined);
    SettingsService.LoadApp().then((a) => { set({ app: a, tab: a.defaultTab as any }); setLogLimit(a.maxLogLines); }).catch(() => undefined);
    DepsService.CheckDeps().then((d) => set({ deps: d })).catch(() => undefined);
  }, [set, setLogLimit]);

  useEffect(() => {
    document.documentElement.dataset.theme = app.theme;
    document.documentElement.dataset.accent = app.accent;
  }, [app.theme, app.accent]);

  const missing = deps?.missing ?? [];

  return (
    <div className="app">
      <Sidebar />
      <main className="main">
        <header className="topbar">
          <div>
            <div className="eyebrow">ytdlp-studio</div>
            <h1>{TITLES[tab]}</h1>
          </div>
          <div className="inline">
            {tab === "analyze" && <span className="tag info">{mode === "audio" ? "Ses modu" : mode === "video" ? "Video modu" : "Altyazı modu"}</span>}
            <button className="btn ghost" onClick={() => set({ tab: "settings", settingsSection: "deps" })}>Bileşenler</button>
          </div>
        </header>

        {missing.length > 0 && (
          <div className="banner">
            <span>Eksik bileşenler: {missing.join(", ")}</span>
            <button className="btn danger" disabled={installing}
              onClick={async () => {
                set({ installing: true });
                try { set({ deps: await DepsService.InstallDeps(), notice: "Bileşenler hazır." }); }
                catch (e) { set({ notice: String(e) }); }
                finally { set({ installing: false }); }
              }}>{installing ? "Kuruluyor…" : "Otomatik Kur"}</button>
          </div>
        )}
        {notice && <div className="notice" onClick={() => set({ notice: undefined })}>{notice}</div>}

        <div className="page">
          {tab === "analyze" && (
            <>
              <PasteBar />
              <div className="analyze-grid">
                <div className="analyze-left">
                  <PreviewList />
                  {mode !== "audio" && <SubtitlePicker />}
                </div>
                <OptionsPanel />
              </div>
              <DownloadButton />
            </>
          )}
          {tab === "queue" && <QueuePanel />}
          {tab === "settings" && <SettingsPage />}
          {tab === "logs" && <LogsPage />}
          {tab === "about" && <AboutPage />}
        </div>
      </main>
      <Toasts />
    </div>
  );
}
