// ytdlp-studio:generated v1
// ytdlp-studio:format v1

export function fmtDuration(sec: number): string {
  if (!sec || sec <= 0) return "—";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return m + ":" + String(s).padStart(2, "0");
}

export function fmtSpeed(bps: number): string {
  if (!bps || bps <= 0) return "";
  if (bps < 1024) return Math.round(bps) + " B/s";
  if (bps < 1024 * 1024) return (bps / 1024).toFixed(1) + " KB/s";
  return (bps / (1024 * 1024)).toFixed(1) + " MB/s";
}

export function fmtEta(sec: number): string {
  if (!sec || sec <= 0) return "";
  const s = Math.ceil(sec);
  if (s < 60) return s + " sn";
  const m = Math.floor(s / 60);
  const rem = s % 60;
  if (m < 60) return m + ":" + String(rem).padStart(2, "0");
  const h = Math.floor(m / 60);
  return h + ":" + String(m % 60).padStart(2, "0") + ":" + String(rem).padStart(2, "0");
}

export const STATE_LABEL: Record<string, string> = {
  queued: "Sırada",
  downloading: "İndiriliyor",
  converting: "Dönüştürülüyor",
  done: "Tamamlandı",
  error: "Hata",
  canceled: "İptal",
};

export function stateTagClass(state: string): string {
  switch (state) {
    case "done":
      return "tag good";
    case "error":
      return "tag bad";
    case "canceled":
      return "tag warn";
    case "downloading":
    case "converting":
      return "tag info";
    default:
      return "tag";
  }
}
