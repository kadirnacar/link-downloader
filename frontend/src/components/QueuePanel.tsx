// ytdlp-studio:generated v1
import { DownloadService } from "../api";
import { useStore } from "../store";
import { useTasks } from "../taskStore";
import { fmtEta, fmtSpeed, pct, STATE_LABEL, stateClass } from "../lib/format";

export function QueuePanel() {
  const tasks = useTasks((s) => s.tasks);
  const order = useTasks((s) => s.order);
  const removeOne = useTasks((s) => s.removeOne);
  const clearFinished = useTasks((s) => s.clearFinished);
  const clearAll = useTasks((s) => s.clearAll);
  const batches = useStore((s) => s.batches);
  const app = useStore((s) => s.app);

  const ids = new Set<string>();
  order.forEach((id) => { const b = tasks[id]?.batchId; if (b) ids.add(b); });
  const list = [...ids].map((id) => batches[id]).filter(Boolean);

  const total = list.reduce((a, b) => a + b.total, 0);
  const done = list.reduce((a, b) => a + b.completed, 0);
  const failed = list.reduce((a, b) => a + b.failed, 0);
  const current = list.reduce((a, b) => a + b.current, 0);
  const percent = total > 0 ? (current / total) * 100 : 0;
  const finished = list.length > 0 && list.every((b) => b.done);

  async function clear(kind: "finished" | "all") {
    if (app.confirmClearQueue && !window.confirm(kind === "all" ? "Tüm kuyruk temizlensin mi?" : "Bitenler temizlensin mi?")) return;
    if (kind === "all") { await DownloadService.ClearAll(); clearAll(); }
    else { await DownloadService.ClearFinished(); clearFinished(); }
  }

  if (order.length === 0) return <section className="card empty">Kuyruk boş. Analiz ekranından indirme başlatın.</section>;

  return (
    <section className="queue-panel">
      <div className="card queue-summary">
        <div className="card-head">
          <h3>{finished ? (failed > 0 ? `Tamamlandı · ${done} başarılı, ${failed} hatalı` : "✓ İndirme tamamlandı") : `İndiriliyor · ${current}/${total}`}</h3>
          <div className="inline">
            <button className="btn small" onClick={() => void DownloadService.PauseAll()}>Tümünü duraklat</button>
            <button className="btn small" onClick={() => void DownloadService.ResumeAll()}>Tümünü sürdür</button>
            <button className="btn small danger" onClick={() => void DownloadService.CancelAll()}>Tümünü iptal</button>
            <button className="btn small" onClick={() => void clear("finished")}>Bitenleri temizle</button>
            <button className="btn small" onClick={() => void clear("all")}>Tümünü temizle</button>
          </div>
        </div>
        <div className="meter"><span style={{ width: pct(percent) + "%" }} /></div>
        <div className="hint">%{Math.round(pct(percent))} · {done} başarılı · {failed} hatalı · {total} toplam</div>
      </div>

      <div className="rows queue-rows">
        {order.map((id) => {
          const t = tasks[id];
          if (!t) return null;
          const active = t.state === "queued" || t.state === "downloading" || t.state === "converting";
          const finishedTask = t.state === "done" || t.state === "error" || t.state === "canceled";
          return (
            <div key={id} className="task">
              <div className="task-line">
                <span className="title">{t.title || id}</span>
                <span className={stateClass(t.state)}>{STATE_LABEL[t.state] ?? t.state}</span>
                {t.state === "downloading" && <span className="meta">{fmtSpeed(t.speedBps)} · {fmtEta(t.etaSec)}</span>}
                <span className="task-btns">
                  {active && <button className="btn small" onClick={() => void DownloadService.Pause(id)}>Duraklat</button>}
                  {t.state === "paused" && <button className="btn small" onClick={() => void DownloadService.Resume(id)}>Devam</button>}
                  {(active || t.state === "paused") && <button className="btn small danger" onClick={() => void DownloadService.Cancel(id)}>İptal</button>}
                  {(t.state === "error" || t.state === "canceled") && <button className="btn small" onClick={() => void DownloadService.Retry(id)}>Yeniden</button>}
                  {t.state === "done" && <button className="btn small" onClick={() => void DownloadService.Reveal(t.filePath ?? "")}>Klasörde göster</button>}
                  {finishedTask && <button className="btn small ghost" onClick={async () => { await DownloadService.Remove(id); removeOne(id); }}>Sil</button>}
                </span>
              </div>
              <div className={"bar " + t.state}><div className="fill" style={{ width: pct(t.percent) + "%" }} /></div>
              {t.error && <div className="error small">{t.error}</div>}
            </div>
          );
        })}
      </div>
    </section>
  );
}
