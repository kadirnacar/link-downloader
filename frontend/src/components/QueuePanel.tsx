// ytdlp-studio:generated v1
// ytdlp-studio:queue v2
import { DownloadService } from "../api";
import { useTasks } from "../taskStore";
import { useStore } from "../store";

function fmtSpeed(bps: number): string {
  if (!bps || bps <= 0) return "";
  return (bps / (1024 * 1024)).toFixed(1) + " MB/s";
}

const STATE_LABEL: Record<string, string> = {
  queued: "Sırada",
  downloading: "İndiriliyor",
  converting: "Dönüştürülüyor",
  paused: "Duraklatıldı",
  done: "Tamamlandı",
  error: "Hata",
  canceled: "İptal",
};

export function QueuePanel() {
  const tasks = useTasks((s) => s.tasks);
  const order = useTasks((s) => s.order);
  const removeOne = useTasks((s) => s.removeOne);
  const clearFinished = useTasks((s) => s.clearFinished);
  const clearAll = useTasks((s) => s.clearAll);
  const batches = useStore((s) => s.batches);

  if (order.length === 0) {
    return <section className="preview empty">Kuyruk boş. Analiz sekmesinden indirme başlat.</section>;
  }

  const activeBatchIds = new Set<string>();
  for (const id of order) {
    const t = tasks[id];
    if (t?.batchId) activeBatchIds.add(t.batchId);
  }
  const activeBatches = [...activeBatchIds]
    .map((id) => batches[id])
    .filter((b): b is NonNullable<typeof b> => Boolean(b));

  async function handleClearFinished() {
    try {
      await DownloadService.ClearFinished();
    } catch {
      // yoksay
    }
    clearFinished();
  }

  async function handleClearAll() {
    try {
      await DownloadService.ClearAll();
    } catch {
      // yoksay
    }
    clearAll();
  }

  async function handleCancelAll() {
    try {
      await DownloadService.CancelAll();
    } catch {
      // yoksay
    }
  }

  async function handleRemove(id: string) {
    try {
      await DownloadService.Remove(id);
    } catch {
      // yoksay
    }
    removeOne(id);
  }

  return (
    <section className="queue-panel">
      <div className="preview-head queue-head">
        <b>Kuyruk ({order.length})</b>
        <div className="queue-actions">
          <button className="ghost" onClick={() => void handleCancelAll()}>
            Tümünü iptal et
          </button>
          <button className="ghost" onClick={() => void handleClearFinished()}>
            Bitenleri temizle
          </button>
          <button className="ghost" onClick={() => void handleClearAll()}>
            Tümünü temizle
          </button>
        </div>
      </div>

      {activeBatches.map((b) => {
        const pct = b.total > 0 ? Math.round((b.current / b.total) * 100) : 0;
        return (
          <div key={b.batchId} className="batch-card">
            <div className="batch-head">
              <b>
                {b.done
                  ? b.failed > 0
                    ? `Tamamlandı · ${b.completed} başarılı, ${b.failed} hatalı`
                    : "✓ İndirme tamamlandı"
                  : `İndiriliyor · ${b.current}/${b.total}`}
              </b>
              <span className="muted">%{pct}</span>
            </div>
            <div className="bar">
              <div className="fill" style={{ width: Math.min(100, pct) + "%" }} />
            </div>
          </div>
        );
      })}

      <div className="rows">
        {order.map((id) => {
          const t = tasks[id];
          if (!t) return null;
          const active = t.state === "queued" || t.state === "downloading" || t.state === "converting";
          const finished = t.state === "done" || t.state === "canceled" || t.state === "error";
          return (
            <div key={id} className="task">
              <div className="task-line">
                <span className="title">{t.title || id}</span>
                <span className={"badge " + t.state}>{STATE_LABEL[t.state] ?? t.state}</span>
                {t.state === "downloading" && (
                  <span className="meta">
                    {fmtSpeed(t.speedBps)}
                    {t.etaSec > 0 ? " · " + Math.ceil(t.etaSec) + " sn" : ""}
                  </span>
                )}
                <span className="task-btns">
                  {active && (
                    <>
                      <button className="ghost" onClick={() => void DownloadService.Pause(id)}>
                        Duraklat
                      </button>
                      <button className="ghost" onClick={() => void DownloadService.Cancel(id)}>
                        İptal
                      </button>
                    </>
                  )}
                  {t.state === "paused" && (
                    <>
                      <button className="ghost" onClick={() => void DownloadService.Resume(id)}>
                        Devam
                      </button>
                      <button className="ghost" onClick={() => void DownloadService.Cancel(id)}>
                        İptal
                      </button>
                    </>
                  )}
                  {(t.state === "error" || t.state === "canceled") && (
                    <button className="ghost" onClick={() => void DownloadService.Retry(id)}>
                      Yeniden
                    </button>
                  )}
                  {t.state === "done" && (
                    <button className="ghost" onClick={() => void DownloadService.Reveal(t.filePath ?? "")}>
                      Finder'da göster
                    </button>
                  )}
                  {finished && (
                    <button className="ghost" onClick={() => void handleRemove(id)}>
                      Sil
                    </button>
                  )}
                </span>
              </div>
              <div className="bar">
                <div className="fill" style={{ width: Math.min(100, Math.max(0, t.percent)) + "%" }} />
              </div>
              {t.error && <div className="error small">{t.error}</div>}
            </div>
          );
        })}
      </div>
    </section>
  );
}
