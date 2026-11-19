// ytdlp-studio:generated v1
import { DownloadService } from "../api";
import { useTasks } from "../taskStore";

function fmtSpeed(bps: number): string {
  if (!bps || bps <= 0) return "";
  return (bps / (1024 * 1024)).toFixed(1) + " MB/s";
}

const STATE_LABEL: Record<string, string> = {
  queued: "Sırada",
  downloading: "İndiriliyor",
  converting: "Dönüştürülüyor",
  done: "Tamamlandı",
  error: "Hata",
  canceled: "İptal",
};

export function QueuePanel() {
  const tasks = useTasks((s) => s.tasks);
  const order = useTasks((s) => s.order);
  const clearFinished = useTasks((s) => s.clearFinished);

  if (order.length === 0) {
    return <section className="preview empty">Kuyruk boş. Analiz sekmesinden indirme başlat.</section>;
  }

  return (
    <section className="queue-panel">
      <div className="preview-head">
        <b>Kuyruk ({order.length})</b>
        <button className="ghost" onClick={clearFinished}>
          Bitenleri temizle
        </button>
      </div>
      <div className="rows">
        {order.map((id) => {
          const t = tasks[id];
          if (!t) return null;
          const active = t.state === "queued" || t.state === "downloading" || t.state === "converting";
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
                {active && (
                  <button className="ghost" onClick={() => void DownloadService.Cancel(id)}>
                    İptal
                  </button>
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
