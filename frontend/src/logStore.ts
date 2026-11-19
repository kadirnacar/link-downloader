// ytdlp-studio:generated v1
import { create } from "zustand";
import type { LogLine } from "./types";

interface LogState {
  lines: LogLine[];
  limit: number;
  push: (l: LogLine) => void;
  setLimit: (n: number) => void;
  clear: () => void;
}

export const useLogs = create<LogState>((set) => ({
  lines: [], limit: 2000,
  push: (l) => set((s) => {
    const lines = [...s.lines, l];
    return { lines: lines.length > s.limit ? lines.slice(lines.length - s.limit) : lines };
  }),
  setLimit: (n) => set({ limit: n }),
  clear: () => set({ lines: [] }),
}));
