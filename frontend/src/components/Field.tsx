// ytdlp-studio:generated v1
import type { FieldDef } from "../settings/catalog";
import { DownloadService } from "../api";

interface Props {
  def: FieldDef;
  value: any;
  onChange: (v: any) => void;
}

export function Field({ def, value, onChange }: Props) {
  const id = "f_" + def.k;
  const multi: string[] = typeof value === "string" && value ? value.split(",").map((s) => s.trim()) : [];

  async function pick(kind: "dir" | "file") {
    try {
      const p = kind === "dir" ? await DownloadService.PickFolder() : await DownloadService.PickFile();
      if (p) onChange(p);
    } catch { /* iptal */ }
  }

  return (
    <div className={"field" + (def.t === "bool" ? " field-bool" : "")}>
      {def.t === "bool" ? (
        <label className="switch" htmlFor={id}>
          <input id={id} type="checkbox" checked={Boolean(value)} onChange={(e) => onChange(e.target.checked)} />
          <span>{def.label}</span>
        </label>
      ) : (
        <label htmlFor={id}>{def.label}</label>
      )}

      {def.t === "text" && (
        <input id={id} value={String(value ?? "")} placeholder={def.ph} onChange={(e) => onChange(e.target.value)} />
      )}
      {def.t === "num" && (
        <input id={id} type="number" min={def.min} max={def.max} value={Number(value ?? 0)}
          onChange={(e) => onChange(Number(e.target.value))} />
      )}
      {def.t === "select" && (
        <select id={id} value={String(value ?? "")}
          onChange={(e) => {
            const raw = e.target.value;
            const choice = def.choices?.find((c) => String(c.v) === raw);
            onChange(typeof choice?.v === "number" ? Number(raw) : raw);
          }}>
          {def.choices?.map((c) => <option key={String(c.v)} value={String(c.v)}>{c.l}</option>)}
        </select>
      )}
      {def.t === "path" && (
        <div className="path-row">
          <input id={id} value={String(value ?? "")} placeholder="Seçilmedi" onChange={(e) => onChange(e.target.value)} />
          <button className="btn" onClick={() => void pick(def.k === "cookiesFile" ? "file" : "dir")}>Seç…</button>
        </div>
      )}
      {def.t === "multi" && (
        <div className="chips">
          {def.choices?.map((c) => {
            const key = String(c.v);
            const on = multi.includes(key);
            return (
              <button key={key} type="button" className={on ? "chip on" : "chip"}
                onClick={() => {
                  const next = on ? multi.filter((m) => m !== key) : [...multi, key];
                  onChange(next.join(","));
                }}>{c.l}</button>
            );
          })}
        </div>
      )}
      {(def.help || def.flag) && (
        <div className="hint">{def.help}{def.help && def.flag ? " · " : ""}{def.flag && <code>{def.flag}</code>}</div>
      )}
    </div>
  );
}
