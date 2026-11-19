// ytdlp-studio:generated v1
// ytdlp-studio:about v2
import { useStore } from "../store";
import { BRAND } from "../lib/brand";

export function AboutPage() {
  const deps = useStore((s) => s.deps);
  return (
    <section className="card about">
      <div className="card-head">
        <h3>{BRAND.display}</h3>
        <span className="tag info">{BRAND.company}</span>
      </div>
      <p className="hint">
        yt-dlp tabanlı ses, video ve altyazı indirme stüdyosu. Playlist analizi, kuyruk yönetimi
        ve ayrıntılı yt-dlp ayarları sunar.
      </p>
      <div className="status-row"><span>Sürüm</span><strong>{BRAND.version}</strong></div>
      <div className="status-row"><span>Geliştirici</span><strong>{BRAND.developer}</strong></div>
      <div className="status-row"><span>Şirket</span><strong>{BRAND.company}</strong></div>
      <div className="status-row">
        <span>E-posta</span>
        <a href={`mailto:${BRAND.email}`}><code>{BRAND.email}</code></a>
      </div>
      <div className="status-row"><span>Bundle ID</span><code>{BRAND.bundleId}</code></div>
      <hr className="divider" />
      <div className="status-row"><span>yt-dlp sürümü</span><strong>{deps?.ytDlpVersion || "—"}</strong></div>
      <div className="status-row"><span>ffmpeg</span><strong>{deps?.ffmpeg ? "hazır" : "eksik"}</strong></div>
      <div className="status-row"><span>ffprobe</span><strong>{deps?.ffprobe ? "hazır" : "eksik"}</strong></div>
      <div className="status-row"><span>JS runtime</span><strong>{deps?.jsRuntime || "—"}</strong></div>
      <hr className="divider" />
      <div className="hint">{BRAND.copyright}</div>
      <div className="hint">İndirilen içeriklerin telif hakkı sorumluluğu kullanıcıya aittir.</div>
    </section>
  );
}
