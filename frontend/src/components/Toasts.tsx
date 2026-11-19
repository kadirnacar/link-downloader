// ytdlp-studio:generated v1
// ytdlp-studio:toasts v2
import { useEffect, useState } from "react";
import { Events } from "@wailsio/runtime";
import type { BatchProgress } from "../types";

interface ToastItem {
  id: number;
  message: string;
  kind: "" | "good" | "bad";
}

let toastSeq = 0;

export function Toasts() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  useEffect(() => {
    const off = Events.On("batch:completed", (ev) => {
      const b = ev.data as BatchProgress;
      if (!b) return;
      if (b.failed > 0) {
        pushToast(`İndirme bitti: ${b.completed} başarılı, ${b.failed} hatalı.`, "bad");
      } else {
        pushToast(`İndirme tamamlandı: ${b.completed}/${b.total} dosya hazır.`, "good");
      }
    });
    return () => {
      off();
    };
  }, []);

  function pushToast(message: string, kind: "" | "good" | "bad") {
    const id = ++toastSeq;
    setToasts((prev) => [...prev, { id, message, kind }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  }

  if (toasts.length === 0) return null;

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
