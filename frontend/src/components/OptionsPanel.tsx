// ytdlp-studio:generated v1
// ytdlp-studio:options v1
import { DownloadService } from "../api";
import { useStore } from "../store";
import type { DownloadOptions } from "../types";

const NAME_PRESETS = [
  "%(playlist_index)03d - %(title)s.%(ext)s",
  "%(title)s.%(ext)s",
  "%(uploader)s/%(title)s.%(ext)s",
];

export function OptionsPanel() {
  const options = useStore((s) => s.options);
  const set = useStore((s) => s.set);
  const upd = (p: Partial<DownloadOptions>) => set({ options: { ...options, ...p } });

  async function pickFolder() {
    try {
      const dir = await DownloadService.PickFolder();
      if (dir) upd({ outputDir: dir });
    } catch {
      // kullanıcı dialogu iptal etti
    }
  }

  return (
    <aside className="options">
      <div className="card-head">
        <h3>İndirme Kuralları</h3>
        <span className="tag">Ayarlar</span>
      </div>

      <div className="seg">
        <button className={options.mode === "audio" ? "active" : ""} onClick={() => upd({ mode: "audio" })}>
          🎵 Ses
        </button>
        <button className={options.mode === "video" ? "active" : ""} onClick={() => upd({ mode: "video" })}>
          🎬 Video
        </button>
      </div>

      {options.mode === "audio" ? (
        <>
          <label>
            Format
            <select value={options.audioFormat} onChange={(e) => upd({ audioFormat: e.target.value })}>
              {["mp3", "m4a", "opus", "flac", "wav"].map((f) => (
                <option key={f} value={f}>
                  {f.toUpperCase()}
                </option>
              ))}
            </select>
          </label>
          <label>
            Kalite
            <select value={options.audioQuality} onChange={(e) => upd({ audioQuality: e.target.value })}>
              <option value="0">En iyi (VBR)</option>
              {["320K", "256K", "192K", "128K"].map((q) => (
                <option key={q} value={q}>
                  {q}
                </option>
              ))}
            </select>
          </label>
        </>
      ) : (
        <>
          <label>
            Çözünürlük
            <select value={options.videoHeight} onChange={(e) => upd({ videoHeight: Number(e.target.value) })}>
              <option value={0}>En iyi</option>
              {[2160, 1440, 1080, 720, 480].map((h) => (
                <option key={h} value={h}>
                  {h}p
                </option>
              ))}
            </select>
          </label>
          <label>
            Kap
            <select value={options.videoContainer} onChange={(e) => upd({ videoContainer: e.target.value })}>
              {["mp4", "mkv", "webm"].map((c) => (
                <option key={c} value={c}>
                  {c.toUpperCase()}
                </option>
              ))}
            </select>
          </label>
        </>
      )}

      <label>
        Klasör
        <div className="folder-row">
          <input readOnly value={options.outputDir} placeholder="Seçilmedi" />
          <button className="btn" onClick={() => void pickFolder()}>
            Seç…
          </button>
        </div>
      </label>

      <label>
        Dosya adı
        <select value={options.nameTemplate} onChange={(e) => upd({ nameTemplate: e.target.value })}>
          {NAME_PRESETS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </label>

      <label className="check">
        <input
          type="checkbox"
          checked={options.embedThumbnail}
          onChange={(e) => upd({ embedThumbnail: e.target.checked })}
        />
        Kapak göm
      </label>
      <label className="check">
        <input
          type="checkbox"
          checked={options.embedMetadata}
          onChange={(e) => upd({ embedMetadata: e.target.checked })}
        />
        Metadata göm
      </label>

      <details>
        <summary>Gelişmiş</summary>
        <label>
          Hız limiti
          <input
            placeholder="ör. 5M (boş = limitsiz)"
            value={options.rateLimit}
            onChange={(e) => upd({ rateLimit: e.target.value })}
          />
        </label>
        <label>
          Eşzamanlı parça
          <select
            value={options.concurrentFragments}
            onChange={(e) => upd({ concurrentFragments: Number(e.target.value) })}
          >
            {[1, 2, 4, 8].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <label>
          Çerezler
          <select
            value={options.cookiesBrowser}
            onChange={(e) => upd({ cookiesBrowser: e.target.value })}
          >
            <option value="">Kullanma</option>
            {["chrome", "safari", "firefox", "brave", "edge"].map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </select>
        </label>
      </details>
    </aside>
  );
}
