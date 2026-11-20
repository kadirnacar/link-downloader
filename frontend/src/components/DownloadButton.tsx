// ytdlp-studio:generated v1
import { useState } from "react";
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
  const [starting, setStarting] = useState(false);

  const entries = (info?.entries ?? []).filter((e) => selected.has(e.id) && e.available);
  const ready = entries.length > 0 && options.outputDir.trim() !== "";
  const label = options.mode === "subtitle" ? "altyazıyı indir" : options.mode === "audio" ? "sesi indir" : "videoyu indir";

  async function start() {
    if (starting) return;
    setStarting(true);
    set({ error: undefined });
    try {
      const batch: BatchInfo = {
        title: info?.title || entries[0]?.title || "İndirme",
        id: info?.id || "",
        kind: (info?.kind ?? "file") === "playlist" || entries.length > 1 ? "playlist" : "file",
      };
      const ids = await DownloadService.Enqueue(entries, options, batch);
      addMany(ids ?? [], entries, undefined, batch.title);
      void SettingsService.Save(options).catch((e) =>
        set({ notice: `İndirme başladı ancak ayarlar kaydedilemedi: ${String(e)}` }),
      );
      set({ tab: "queue" });
    } catch (e) {
      set({ error: String(e) });
    } finally {
      setStarting(false);
    }
  }

  return (
    <div className="actionbar">
      <span className="hint">{ready ? options.outputDir : "İndirme klasörü seçilmedi"}</span>
      <button className="btn primary download" disabled={!ready || starting} onClick={() => void start()}>
        {starting ? "Kuyruğa ekleniyor…" : `⬇ ${entries.length} öğe ${label}`}
      </button>
    </div>
  );
}
