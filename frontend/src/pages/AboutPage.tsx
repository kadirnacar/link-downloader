// ytdlp-studio:generated v1
import { useStore } from "../store";

export function AboutPage() {
  const deps = useStore((s) => s.deps);
  return (
    <section className="card about">
      <div className="card-head"><h3>ytdlp-studio</h3><span className="tag info">Wails v3 · Go · React</span></div>
      <p className="hint">yt-dlp tabanlı ses, video ve altyazı indirme stüdyosu. Playlist analizi, kuyruk yönetimi ve ayrıntılı yt-dlp ayarları sunar.</p>
      <div className="status-row"><span>yt-dlp sürümü</span><strong>{deps?.ytDlpVersion || "—"}</strong></div>
      <div className="status-row"><span>ffmpeg</span><strong>{deps?.ffmpeg ? "hazır" : "eksik"}</strong></div>
      <div className="status-row"><span>JS runtime</span><strong>{deps?.jsRuntime || "—"}</strong></div>
      <hr className="divider" />
      <div className="hint">İndirilen içeriklerin telif hakkı sorumluluğu kullanıcıya aittir.</div>
    </section>
  );
}
