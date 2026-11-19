// ytdlp-studio:generated v1
import { useState } from "react";
import { useLogs } from "../logStore";

export function LogsPage() {
  const lines = useLogs((s) => s.lines);
  const clear = useLogs((s) => s.clear);
  const [q, setQ] = useState("");
  const visible = lines.filter((l) => l.text.toLowerCase().includes(q.toLowerCase()));

  return (
    <section className="card logs">
      <div className="card-head">
        <h3>Günlük ({visible.length})</h3>
        <div className="inline">
          <input className="filter" placeholder="Filtrele…" value={q} onChange={(e) => setQ(e.target.value)} />
          <button className="btn small" onClick={() => void navigator.clipboard.writeText(visible.map((l) => `[${l.time}] ${l.text}`).join("\n"))}>Kopyala</button>
          <button className="btn small ghost" onClick={clear}>Temizle</button>
        </div>
      </div>
      <div className="console tall">
        {visible.map((l, i) => <div key={i}>[{l.time}] {l.text}</div>)}
        {visible.length === 0 && <div className="empty">Kayıt yok.</div>}
      </div>
    </section>
  );
}
