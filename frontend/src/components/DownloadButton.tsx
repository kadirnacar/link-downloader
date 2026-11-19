// ytdlp-studio:generated v1
import { DownloadService, SettingsService } from "../api";
import { useStore } from "../store";
import { useTasks } from "../taskStore";
import type { BatchInfo } from "../types";

export function DownloadButton() {
  const info = useStore((s) => s.info);
  const selected = useStore((s) => s.selected);
  const options = useStore((s) => s.options);
  const set = useStore((s) => s.set);
  const addMany = useTasks((s) => s.addMany);

  const entries = (info?.entries ?? []).filter((e) => selected.has(e.id) && e.available);
  const ready = entries.length > 0 && options.outputDir.trim() !== "";
  const label = options.mode === "subtitle" ? "altyazıyı indir" : options.mode === "audio" ? "sesi indir" : "videoyu indir";

  async function start() {
    set({ error: undefined });
    try {
      const batch: BatchInfo = {
        title: info?.title || entries[0]?.title || "İndirme",
        id: info?.id || "",
        kind: (info?.kind ?? "file") === "playlist" || entries.length > 1 ? "playlist" : "file",
      };
      const ids = await DownloadService.Enqueue(entries, options, batch);
      addMany(ids ?? [], entries, undefined, batch.title);
      void SettingsService.Save(options);
      set({ tab: "queue" });
    } catch (e) {
      set({ error: String(e) });
    }
  }

  return (
    <div className="actionbar">
      <span className="hint">{ready ? options.outputDir : "İndirme klasörü seçilmedi"}</span>
      <button className="btn primary download" disabled={!ready} onClick={() => void start()}>
        ⬇ {entries.length} öğe {label}
      </button>
    </div>
  );
}
