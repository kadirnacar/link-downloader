// ytdlp-studio:generated v1
// ytdlp-studio:toasts v1
import { useEffect, useState } from "react";
import { Events } from "@wailsio/runtime";
import type { TaskProgress } from "../types";

interface ToastItem {
  id: number;
  message: string;
  kind: "" | "good" | "bad";
}

let toastSeq = 0;

export function Toasts() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  useEffect(() => {
    const off = Events.On("task:progress", (ev) => {
      const p = ev.data as TaskProgress;
      if (p.state === "done") {
        pushToast(`"${(p as unknown as { title?: string }).title ?? "Dosya"}" indirildi.`, "good");
      } else if (p.state === "error") {
        pushToast("İndirme hatası: " + (p.error ?? "bilinmiyor"), "bad");
      }
    });
    return off;
  }, []);

  function pushToast(message: string, kind: "" | "good" | "bad") {
    const id = ++toastSeq;
    setToasts((prev) => [...prev, { id, message, kind }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }

  return (
    <div className="toast-wrap">
      {toasts.map((t) => (
        <div key={t.id} className={"toast " + t.kind}>
          {t.message}
        </div>
      ))}
    </div>
  );
}
