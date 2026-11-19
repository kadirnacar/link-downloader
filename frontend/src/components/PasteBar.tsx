// ytdlp-studio:generated v1
// ytdlp-studio:pastebar v1
import { AnalyzeService } from "../api";
import { useStore } from "../store";

export function PasteBar() {
  const url = useStore((s) => s.url);
  const parsed = useStore((s) => s.parsed);
  const scope = useStore((s) => s.scope);
  const analyzing = useStore((s) => s.analyzing);
  const error = useStore((s) => s.error);
  const set = useStore((s) => s.set);

  async function analyze(raw: string, sc: "video" | "playlist") {
    const trimmed = raw.trim();
    if (!trimmed) return;
    set({ analyzing: true, error: undefined, info: undefined });
    try {
      const p = await AnalyzeService.ParseURL(trimmed);
      const info = await AnalyzeService.Analyze(trimmed, sc);
      set({
        url: trimmed,
        parsed: p,
        info: info ?? undefined,
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
      <input
        className="url-input"
        placeholder="YouTube video veya playlist URL'si yapıştır…"
        value={url}
        onChange={(e) => set({ url: e.target.value })}
        onPaste={(e) => {
          const text = e.clipboardData.getData("text");
          if (text.trim().startsWith("http")) {
            e.preventDefault();
            set({ url: text.trim() });
            void analyze(text, scope);
          }
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") void analyze(url, scope);
        }}
        disabled={analyzing}
      />
      <button className="btn primary" onClick={() => void analyze(url, scope)} disabled={analyzing || !url.trim()}>
        {analyzing ? "Analiz ediliyor…" : "Analiz Et"}
      </button>
      {parsed?.ambiguous && (
        <select
          value={scope}
          onChange={(e) => {
            const sc = e.target.value as "video" | "playlist";
            set({ scope: sc });
            void analyze(url, sc);
          }}
        >
          <option value="video">Sadece video</option>
          <option value="playlist">Tüm playlist</option>
        </select>
      )}
      {parsed && !parsed.ambiguous && (
        <span className="chip">
          {parsed.kind === "playlist" ? "Playlist" : parsed.kind === "video" ? "Video" : "Diğer"}
        </span>
      )}
      {parsed?.isMix && <span className="chip warn">⚠ Mix listesi</span>}
      {error && <div className="error">{error}</div>}
    </section>
  );
}
