// ytdlp-studio:generated v1
// ytdlp-studio:previewlist v1
import { useState } from "react";
import { useStore } from "../store";
import { fmtDuration } from "../lib/format";

export function PreviewList() {
  const info = useStore((s) => s.info);
  const selected = useStore((s) => s.selected);
  const set = useStore((s) => s.set);
  const [filter, setFilter] = useState("");

  if (!info) {
    return <section className="preview empty">URL yapıştırdığında içerik önizlemesi burada görünür.</section>;
  }

  const entries = info.entries ?? [];
  const visible = entries.filter((e) => e.title.toLowerCase().includes(filter.toLowerCase()));
  const availableVisible = visible.filter((e) => e.available);
  const allSelected = availableVisible.length > 0 && availableVisible.every((e) => selected.has(e.id));

  function toggle(id: string) {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    set({ selected: next });
  }

  function toggleAll() {
    const next = new Set(selected);
    if (allSelected) availableVisible.forEach((e) => next.delete(e.id));
    else availableVisible.forEach((e) => next.add(e.id));
    set({ selected: next });
  }

  return (
    <section className="preview">
      <div className="card-head">
        <h3>{info.title}</h3>
        <span className="tag info">{entries.length} öğe</span>
      </div>
      <div className="preview-head">
        <label className="select-all">
          <input type="checkbox" checked={allSelected} onChange={toggleAll} />
          <b>Tümünü seç</b>
        </label>
        <input
          className="filter"
          placeholder="Ara…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <span className="count">
          {selected.size}/{entries.length}
        </span>
      </div>
      <div className="rows">
        {visible.map((e) => (
          <label
            key={e.id}
            className={e.available ? "row" : "row unavailable"}
          >
            <input
              type="checkbox"
              checked={selected.has(e.id)}
              disabled={!e.available}
              onChange={() => toggle(e.id)}
            />
            {e.thumbnail ? (
              <img src={e.thumbnail} loading="lazy" alt="" />
            ) : (
              <div className="thumb-placeholder" />
            )}
            <span className="idx">{String(e.index).padStart(3, "0")}</span>
            <span className="title">{e.title}</span>
            <span className="dur">{fmtDuration(e.durationSec)}</span>
          </label>
        ))}
        {visible.length === 0 && (
          <div className="preview empty">Gösterilecek öğe bulunamadı.</div>
        )}
      </div>
    </section>
  );
}
