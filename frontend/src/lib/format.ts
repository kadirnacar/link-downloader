// ytdlp-studio:generated v1
export function fmtDuration(sec: number): string {
  if (!sec || sec <= 0) return "—";
  const t = Math.floor(sec), h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), s = t % 60;
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `${m}:${String(s).padStart(2, "0")}`;
}
export function fmtSpeed(bps: number): string {
  if (!bps || bps <= 0) return "—";
  if (bps >= 1048576) return (bps / 1048576).toFixed(1) + " MB/s";
  return Math.round(bps / 1024) + " KB/s";
}
export function fmtEta(sec: number): string {
  if (!sec || sec <= 0 || !isFinite(sec)) return "—";
  const t = Math.ceil(sec);
  if (t < 60) return t + " sn";
  const m = Math.floor(t / 60);
  return m < 60 ? `${m} dk` : `${Math.floor(m / 60)} sa ${m % 60} dk`;
}
export function pct(v: number): number {
  if (!isFinite(v) || v <= 0) return 0;
  return Math.min(100, v);
}
export const STATE_LABEL: Record<string, string> = {
  queued: "Sırada", downloading: "İndiriliyor", converting: "Dönüştürülüyor",
  paused: "Duraklatıldı", done: "Tamamlandı", error: "Hata", canceled: "İptal",
};
export function stateClass(s: string): string {
  if (s === "done") return "tag good";
  if (s === "error") return "tag bad";
  if (s === "canceled" || s === "paused") return "tag warn";
  if (s === "downloading" || s === "converting") return "tag info";
  return "tag";
}
