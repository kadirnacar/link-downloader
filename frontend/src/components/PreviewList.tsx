// ytdlp-studio:generated v1
import { useState } from "react";
import { useStore } from "../store";
import { fmtDuration } from "../lib/format";

export function PreviewList() {
  const info = useStore((s) => s.info);
  const selected = useStore((s) => s.selected);
  const set = useStore((s) => s.set);
  const [filter, setFilter] = useState("");

  if (!info) return (
    <section className="card preview-empty">
      <div className="preview-empty-icon" aria-hidden="true">↘</div>
      <div className="workspace-kicker">AKILLI İÇERİK ÖNİZLEMESİ</div>
      <h2>İlk bağlantını ekle</h2>
      <p>Video veya playlist bağlantısını yukarıya yapıştır. Başlıkları, süreleri ve kapakları kontrol ettikten sonra indireceğin öğeleri seç.</p>
      <div className="preview-benefits">
        <span>✓ Playlist seçimi</span><span>✓ Ses / video formatları</span><span>✓ Canlı kuyruk takibi</span>
      </div>
    </section>
  );

  const entries = info.entries ?? [];
  const visible = entries.filter((e) => (e.title || "").toLowerCase().includes(filter.toLowerCase()));
  const avail = visible.filter((e) => e.available);
  const all = avail.length > 0 && avail.every((e) => selected.has(e.id));

  const toggle = (id: string) => {
    const next = new Set(selected);
    next.has(id) ? next.delete(id) : next.add(id);
    set({ selected: next });
  };
  const toggleAll = () => {
    const next = new Set(selected);
    avail.forEach((e) => (all ? next.delete(e.id) : next.add(e.id)));
    set({ selected: next });
  };

  return (
    <section className="card preview">
      <div className="card-head">
        <label className="select-all">
          <input type="checkbox" checked={all} onChange={toggleAll} />
          <h3 title={info.title}>{info.title}</h3>
        </label>
        <div className="inline">
          <input className="filter" placeholder="Ara…" value={filter} onChange={(e) => setFilter(e.target.value)} />
          <span className="tag">{selected.size}/{entries.length}</span>
        </div>
      </div>
      <div className="rows">
        {visible.map((e) => (
          <label key={e.id} className={e.available ? "row" : "row unavailable"}>
            <input type="checkbox" checked={selected.has(e.id)} disabled={!e.available} onChange={() => toggle(e.id)} />
            {e.thumbnail ? <img src={e.thumbnail} loading="lazy" alt="" /> : <div className="thumb-placeholder" />}
            <span className="idx">{String(e.index).padStart(3, "0")}</span>
            <span className="title">{e.title}</span>
            <span className="dur">{fmtDuration(e.durationSec)}</span>
          </label>
        ))}
        {visible.length === 0 && <div className="empty">Eşleşen öğe yok.</div>}
      </div>
    </section>
  );
}
