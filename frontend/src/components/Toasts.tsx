// ytdlp-studio:generated v1
import { useEffect, useState } from "react";
import { Events } from "@wailsio/runtime";
import { useStore } from "../store";
import type { BatchProgress } from "../types";

interface T { id: number; text: string; kind: string; }
let seq = 0;

export function Toasts() {
  const [items, setItems] = useState<T[]>([]);
  const notifications = useStore((s) => s.app.notifications);

  useEffect(() => {
    const off = Events.On("batch:completed", (ev) => {
      const b = ev.data as BatchProgress;
      if (!b || !notifications) return;
      const id = ++seq;
      const text = b.failed > 0
        ? `İndirme bitti: ${b.completed} başarılı, ${b.failed} hatalı.`
        : `İndirme tamamlandı: ${b.completed}/${b.total} hazır.`;
      setItems((p) => [...p, { id, text, kind: b.failed > 0 ? "bad" : "good" }]);
      setTimeout(() => setItems((p) => p.filter((x) => x.id !== id)), 5000);
    });
    return () => { off(); };
  }, [notifications]);

  if (items.length === 0) return null;
  return (
    <div className="toast-wrap">
      {items.map((t) => <div key={t.id} className={"toast " + t.kind}>{t.text}</div>)}
    </div>
  );
}
