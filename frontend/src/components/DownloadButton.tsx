// ytdlp-studio:generated v1
import { DownloadService, SettingsService } from "../api";
import { useStore } from "../store";
import { useTasks } from "../taskStore";

export function DownloadButton() {
  const info = useStore((s) => s.info);
  const selected = useStore((s) => s.selected);
  const options = useStore((s) => s.options);
  const set = useStore((s) => s.set);
  const addMany = useTasks((s) => s.addMany);

  const entries = (info?.entries ?? []).filter((e) => selected.has(e.id) && e.available);
  const ready = entries.length > 0 && options.outputDir.trim() !== "";

  async function start() {
    set({ error: undefined });
    try {
       const ids = await DownloadService.Enqueue(entries, options);
       addMany(ids ?? [], entries);
      void SettingsService.Save(options);
      set({ tab: "queue" });
    } catch (e) {
      set({ error: String(e) });
    }
  }

  return (
    <button className="download" disabled={!ready} onClick={() => void start()}>
      ⬇ {entries.length} öğeyi indir
    </button>
  );
}
