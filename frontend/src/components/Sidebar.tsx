// ytdlp-studio:generated v1
import { useStore } from "../store";
import { useTasks } from "../taskStore";
import type { Tab } from "../types";

const NAV: { id: Tab; icon: string; label: string }[] = [
  { id: "analyze", icon: "◈", label: "Analiz" },
  { id: "queue", icon: "⇩", label: "Kuyruk" },
  { id: "settings", icon: "⚙", label: "Ayarlar" },
  { id: "logs", icon: "≡", label: "Günlük" },
  { id: "about", icon: "ⓘ", label: "Hakkında" },
];

export function Sidebar() {
  const tab = useStore((s) => s.tab);
  const app = useStore((s) => s.app);
  const deps = useStore((s) => s.deps);
  const set = useStore((s) => s.set);
  const patchApp = useStore((s) => s.patchApp);
  const active = useTasks((s) => s.order.filter((id) => {
    const t = s.tasks[id];
    return t && (t.state === "downloading" || t.state === "converting" || t.state === "queued");
  }).length);

  return (
    <aside className={app.sidebarCollapsed ? "sidebar collapsed" : "sidebar"}>
      <div className="brand">
        <div className="brand-mark" aria-hidden="true"><span>↓</span></div>
        {!app.sidebarCollapsed && (
          <div><strong>Link Downloader</strong><span>yt-dlp Studio · Bengsoft</span></div>
        )}
      </div>

      <div className="nav-wrap">
        {!app.sidebarCollapsed && <div className="nav-label">Ana menü</div>}
        <nav className="nav">
          {NAV.map((n) => (
            <button key={n.id} className={tab === n.id ? "active" : ""} onClick={() => set({ tab: n.id })} title={n.label}>
              <span className="ico">{n.icon}</span>
              {!app.sidebarCollapsed && <span className="nav-text">{n.label}</span>}
              {n.id === "queue" && active > 0 && <span className="nav-badge">{active}</span>}
            </button>
          ))}
        </nav>
      </div>

      {!app.sidebarCollapsed && (
        <div className="sidebar-bottom">
          <strong>Sistem durumu</strong>
          <div className="dep-row"><span>yt-dlp</span><i className={deps?.ytDlp ? "dot online" : "dot"} /></div>
          <div className="dep-row"><span>ffmpeg</span><i className={deps?.ffmpeg ? "dot online" : "dot"} /></div>
          <div className="dep-row"><span>ffprobe</span><i className={deps?.ffprobe ? "dot online" : "dot"} /></div>
          <div className="dep-row"><span>JS runtime</span><i className={deps?.jsRuntime ? "dot online" : "dot"} /></div>
          {deps?.ytDlpVersion && <div className="hint">yt-dlp {deps.ytDlpVersion}</div>}
        </div>
      )}

      <button className="collapse-btn" onClick={() => patchApp({ sidebarCollapsed: !app.sidebarCollapsed })}>
        {app.sidebarCollapsed ? "»" : "«"}
      </button>
    </aside>
  );
}
