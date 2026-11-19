// ytdlp-studio:generated v1
// ytdlp-studio:queue v1
import { DownloadService } from "../api";
import { useTasks } from "../taskStore";
import { useStore } from "../store";
import { fmtEta, fmtSpeed, STATE_LABEL, stateTagClass } from "../lib/format";

export function QueuePanel() {
  const tasks = useTasks((s) => s.tasks);
  const order = useTasks((s) => s.order);
  const clearFinished = useTasks((s) => s.clearFinished);
  const batches = useStore((s) => s.batches);

  const activeBatchIds = new Set<string>();
  for (const id of order) {
    const t = tasks[id];
    if (t?.batchId) activeBatchIds.add(t.batchId);
  }

  const activeBatches = [...activeBatchIds]
    .map((id) => batches[id])
    .filter((b): b is NonNullable<typeof b> => !!b);

  const totalItems = activeBatches.reduce((acc, b) => acc + b.total, 0);
  const completedItems = activeBatches.reduce((acc, b) => acc + b.completed, 0);
  const failedItems = activeBatches.reduce((acc, b) => acc + b.failed, 0);
  const currentItems = activeBatches.reduce((acc, b) => acc + b.current, 0);
  const allDone = activeBatches.length > 0 && activeBatches.every((b) => b.done);
  const batchPercent = totalItems > 0 ? (currentItems / totalItems) * 100 : 0;

  if (order.length === 0) {
    return <section className="preview empty">Kuyruk boş. Analiz sekmesinden indirme başlat.</section>;
  }

  return (
    <section className="queue-panel">
      <div className="card-head">
        <h3>Kuyruk ({order.length})</h3>
        <button className="btn ghost small" onClick={clearFinished}>
          Bitenleri temizle
        </button>
      </div>

      {activeBatches.length > 0 && (
        <>
          <div className="batch-summary">
            <div className="card">
              <div className="metric">
                <div>
                  <div className="metric-label">Toplam</div>
                  <div className="metric-value">{totalItems}</div>
                </div>
                <div className="metric-icon">▤</div>
              </div>
            </div>
            <div className="card">
              <div className="metric">
                <div>
                  <div className="metric-label">Tamamlanan</div>
                  <div className="metric-value">{completedItems}</div>
                </div>
                <div className="metric-icon mint">✓</div>
              </div>
            </div>
            <div className="card">
              <div className="metric">
                <div>
                  <div className="metric-label">Başarısız</div>
                  <div className="metric-value">{failedItems}</div>
                </div>
                <div className="metric-icon pink">✕</div>
              </div>
            </div>
            <div className="card">
              <div className="metric">
                <div>
                  <div className="metric-label">İlerleme</div>
                  <div className="metric-value">{batchPercent.toFixed(0)}%</div>
                </div>
                <div className="metric-icon gold">◷</div>
              </div>
              <div className="meter">
                <span style={{ width: Math.min(100, batchPercent) + "%" }} />
              </div>
              {allDone && (
                <div className="hint" style={{ marginTop: "6px", color: "#8ce4b4" }}>
                  ✓ İndirme tamamlandı
                </div>
              )}
            </div>
          </div>
        </>
      )}

      <div className="rows">
        {order.map((id) => {
          const t = tasks[id];
          if (!t) return null;
          const active = t.state === "queued" || t.state === "downloading" || t.state === "converting";
          return (
            <div key={id} className="task">
              <div className="task-line">
                <span className="title">{t.title || id}</span>
                <span className={stateTagClass(t.state)}>{STATE_LABEL[t.state] ?? t.state}</span>
                {t.state === "downloading" && (
                  <span className="meta">
                    {fmtSpeed(t.speedBps)}
                    {t.etaSec > 0 ? " · " + fmtEta(t.etaSec) : ""}
                  </span>
                )}
                {active && (
                  <button className="btn small danger" onClick={() => void DownloadService.Cancel(id)}>
                    İptal
                  </button>
                )}
                {(t.state === "error" || t.state === "canceled") && (
                  <button className="btn small" onClick={() => void DownloadService.Retry(id)}>
                    Yeniden
                  </button>
                )}
                {t.state === "done" && (
                  <button className="btn small" onClick={() => void DownloadService.Reveal(t.filePath ?? "")}>
                    Finder'da göster
                  </button>
                )}
              </div>
              <div className={"bar " + t.state}>
                <div
                  className="fill"
                  style={{ width: Math.min(100, Math.max(0, t.percent)) + "%" }}
                />
              </div>
              {t.error && <div className="error small">{t.error}</div>}
            </div>
          );
        })}
      </div>
    </section>
  );
}
