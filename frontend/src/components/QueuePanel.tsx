// ytdlp-studio:generated v1
// ytdlp-studio:queue v5
import { useState } from "react";
import { DownloadService } from "../api";
import { useStore } from "../store";
import { useTasks } from "../taskStore";
import { fmtEta, fmtSpeed, pct, STATE_LABEL, stateClass } from "../lib/format";

type Pending = { text: string; run: () => void } | null;

export function QueuePanel() {
  const tasks = useTasks((s) => s.tasks);
  const order = useTasks((s) => s.order);
  const upsert = useTasks((s) => s.upsert);
  const removeOne = useTasks((s) => s.removeOne);
  const clearFinishedLocal = useTasks((s) => s.clearFinished);
  const clearAllLocal = useTasks((s) => s.clearAll);
  const batches = useStore((s) => s.batches);
  const upsertBatch = useStore((s) => s.upsertBatch);
  const confirmClear = useStore((s) => s.app.confirmClearQueue);
  const set = useStore((s) => s.set);
  const [pending, setPending] = useState<Pending>(null);
  const [busy, setBusy] = useState(false);

  async function call(name: string, fn: () => Promise<unknown>, after?: () => void) {
    setBusy(true);
    try {
      await fn();
      after?.();
    } catch (e) {
      set({ notice: `${name} başarısız: ${String(e)}` });
    } finally {
      setBusy(false);
    }
  }

  function ask(text: string, run: () => void) {
    if (confirmClear) setPending({ text, run });
    else run();
  }

  const ids = new Set<string>();
  order.forEach((id) => { const b = tasks[id]?.batchId; if (b) ids.add(b); });
  const list = [...ids].map((id) => batches[id]).filter(Boolean);

  const total = list.reduce((a, b) => a + b.total, 0);
  const done = list.reduce((a, b) => a + b.completed, 0);
  const failed = list.reduce((a, b) => a + b.failed, 0);
  const current = list.reduce((a, b) => a + b.current, 0);
  const percent = total > 0 ? list.reduce((sum, batch) => sum + batch.percent * batch.total, 0) / total : 0;
  const finished = list.length > 0 && list.every((b) => b.done);

  if (order.length === 0) {
    return <section className="card empty">Kuyruk boş. Analiz ekranından indirme başlatın.</section>;
  }

  return (
    <section className="queue-panel">
      <div className="card queue-summary">
        <div className="card-head">
          <h3>
            {finished
              ? failed > 0
                ? `Tamamlandı · ${done} başarılı, ${failed} hatalı`
                : "✓ İndirme tamamlandı"
              : `İndiriliyor · ${current}/${total}`}
          </h3>
          <div className="inline">
            <button className="btn small" disabled={busy}
              onClick={() => void call("PauseAll", () => DownloadService.PauseAll(), () => {
                order.forEach((id) => {
                  const t = tasks[id];
                  if (t && (t.state === "queued" || t.state === "downloading" || t.state === "converting")) {
                    upsert({ taskId: id, state: "paused", percent: t.percent, speedBps: 0, etaSec: 0 });
                  }
                });
              })}>Tümünü duraklat</button>

            <button className="btn small" disabled={busy}
              onClick={() => void call("ResumeAll", () => DownloadService.ResumeAll(), () => {
                order.forEach((id) => {
                  const t = tasks[id];
                  if (t && (t.state === "paused" || t.state === "error" || t.state === "canceled")) {
                    upsert({ taskId: id, state: "queued", percent: 0, speedBps: 0, etaSec: 0 });
                  }
                });
              })}>Tümünü sürdür</button>

            <button className="btn small danger" disabled={busy}
              onClick={() => ask("Tüm görevler iptal edilsin mi?", () => {
                void call("CancelAll", () => DownloadService.CancelAll(), () => {
                  order.forEach((id) => {
                    const t = tasks[id];
                    if (t && t.state !== "done") {
                      upsert({ taskId: id, state: "canceled", percent: t.percent, speedBps: 0, etaSec: 0 });
                    }
                  });
                });
              })}>Tümünü iptal</button>

            <button className="btn small" disabled={busy}
              onClick={() => ask("Biten görevler temizlensin mi?", () => {
                void call("ClearFinished", () => DownloadService.ClearFinished(), clearFinishedLocal);
              })}>Bitenleri temizle</button>

            <button className="btn small" disabled={busy}
              onClick={() => ask("Tüm kuyruk temizlensin mi? Aktif indirmeler iptal edilir.", () => {
                void call("ClearAll", () => DownloadService.ClearAll(), clearAllLocal);
              })}>Tümünü temizle</button>
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
          const terminal = t.state === "done" || t.state === "error" || t.state === "canceled";
          return (
            <div key={id} className="task">
              <div className="task-line">
                <span className="title">{t.title || id}</span>
                <span className={stateClass(t.state)}>{STATE_LABEL[t.state] ?? t.state}</span>
                {t.state === "downloading" && (
                  <span className="meta">{fmtSpeed(t.speedBps)} · {fmtEta(t.etaSec)}</span>
                )}
                <span className="task-btns">
                  {active && (
                    <button className="btn small" disabled={busy}
                      onClick={() => void call("Pause", () => DownloadService.Pause(id), () =>
                        upsert({ taskId: id, state: "paused", percent: t.percent, speedBps: 0, etaSec: 0 })
                      )}>Duraklat</button>
                  )}
                  {t.state === "paused" && (
                    <button className="btn small" disabled={busy}
                      onClick={() => void call("Resume", () => DownloadService.Resume(id), () =>
                        upsert({ taskId: id, state: "queued", percent: 0, speedBps: 0, etaSec: 0 })
                      )}>Devam</button>
                  )}
                  {(active || t.state === "paused") && (
                    <button className="btn small danger" disabled={busy}
                      onClick={() => void call("Cancel", () => DownloadService.Cancel(id), () =>
                        upsert({ taskId: id, state: "canceled", percent: t.percent, speedBps: 0, etaSec: 0 })
                      )}>İptal</button>
                  )}
                  {(t.state === "error" || t.state === "canceled") && (
                    <button className="btn small" disabled={busy}
                      onClick={() => void call("Resume", () => DownloadService.Resume(id), () =>
                        upsert({ taskId: id, state: "queued", percent: 0, speedBps: 0, etaSec: 0 })
                      )}>Yeniden</button>
                  )}
                  {t.state === "done" && (
                    <button className="btn small" disabled={busy}
                      onClick={() => void call("Reveal", () => DownloadService.Reveal(t.filePath ?? ""))}>Klasörde göster</button>
                  )}
                  {terminal && (
                    <button className="btn small ghost" disabled={busy}
                      onClick={() => void call("Remove", () => DownloadService.Remove(id), () => removeOne(id))}>Sil</button>
                  )}
                </span>
              </div>
              <div className={"bar " + t.state}><div className="fill" style={{ width: pct(t.percent) + "%" }} /></div>
              {t.error && <div className="error small">{t.error}</div>}
            </div>
          );
        })}
      </div>

      {pending && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal card">
            <div className="card-head"><h3>Onay</h3></div>
            <p className="hint">{pending.text}</p>
            <div className="inline modal-actions">
              <button className="btn" onClick={() => setPending(null)}>Vazgeç</button>
              <button className="btn primary" onClick={() => { const r = pending.run; setPending(null); r(); }}>
                Onayla
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
