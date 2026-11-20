// ytdlp-studio:generated v1
import { AnalyzeService } from "../api";
import { useStore } from "../store";

export function PasteBar() {
  const url = useStore((s) => s.url);
  const parsed = useStore((s) => s.parsed);
  const scope = useStore((s) => s.scope);
  const analyzing = useStore((s) => s.analyzing);
  const error = useStore((s) => s.error);
  const options = useStore((s) => s.options);
  const app = useStore((s) => s.app);
  const set = useStore((s) => s.set);

  async function analyze(raw: string, sc: "video" | "playlist") {
    const trimmed = raw.trim();
    if (!trimmed) return;
    set({ analyzing: true, error: undefined, info: undefined, subs: undefined });
    try {
      const p = await AnalyzeService.ParseURL(trimmed);
      const analyzeScope = options.playlistReverse ? `${sc}-reverse` : sc;
      const info = await AnalyzeService.Analyze(trimmed, analyzeScope, options.playlistItems);
      set({
        url: trimmed, parsed: p, info: info ?? undefined,
        selected: new Set((info?.entries ?? []).filter((e) => e.available).map((e) => e.id)),
      });
    } catch (e) {
      set({ error: String(e) });
    } finally {
      set({ analyzing: false });
    }
  }

  return (
    <section className="pastebar">
      <div className="pastebar-field">
        <input className="url-input" placeholder="YouTube video veya playlist URL'si yapıştır…"
          value={url} disabled={analyzing}
          onChange={(e) => set({ url: e.target.value })}
          onPaste={(e) => {
            const text = e.clipboardData.getData("text").trim();
            if (app.clipboardAutoAnalyze && text.startsWith("http")) {
              e.preventDefault();
              set({ url: text });
              void analyze(text, scope);
            }
          }}
          onKeyDown={(e) => { if (e.key === "Enter") void analyze(url, scope); }} />
      </div>
      <div className="pastebar-side">
        <button className="btn primary pastebar-btn" disabled={analyzing || !url.trim()} onClick={() => void analyze(url, scope)}>
          {analyzing ? "Analiz ediliyor…" : "Analiz Et"}
        </button>
        {parsed?.ambiguous && (
          <select className="pastebar-scope" value={scope} disabled={analyzing}
            onChange={(e) => {
              const sc = e.target.value as "video" | "playlist";
              set({ scope: sc });
              void analyze(url, sc);
            }}>
            <option value="video">Sadece video</option>
            <option value="playlist">Tüm playlist</option>
          </select>
        )}
        {parsed && !parsed.ambiguous && (
          <span className="tag info">{parsed.kind === "playlist" ? "Playlist" : parsed.kind === "video" ? "Video" : "Diğer"}</span>
        )}
        {parsed?.isMix && <span className="tag warn">Mix</span>}
      </div>
      {error && <div className="pastebar-error error">{error}</div>}
    </section>
  );
}
