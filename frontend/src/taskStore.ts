// ytdlp-studio:generated v1
// ytdlp-studio:taskstore v3
import { create } from "zustand";
import type { MediaEntry, TaskProgress } from "./types";

export interface TaskItem extends TaskProgress { title: string; }

interface TaskState {
  tasks: Record<string, TaskItem>;
  order: string[];
  addMany: (ids: string[], entries: MediaEntry[], batchId?: string, batchTitle?: string) => void;
  upsert: (p: TaskProgress) => void;
  removeOne: (id: string) => void;
  clearFinished: () => void;
  clearAll: () => void;
}

const blank = (id: string): TaskItem => ({
  taskId: id, title: id, state: "queued", percent: 0, speedBps: 0, etaSec: 0,
});

export const useTasks = create<TaskState>((set) => ({
  tasks: {}, order: [],
  addMany: (ids, entries, batchId, batchTitle) =>
    set((s) => {
      const tasks = { ...s.tasks };
      const order = [...s.order];
      ids.forEach((id, i) => {
        const prev = tasks[id];
        tasks[id] = {
          ...blank(id), ...prev, taskId: id,
          title: entries[i]?.title || prev?.title || id,
          batchId: prev?.batchId || batchId, batchTitle: prev?.batchTitle || batchTitle,
        };
        if (!order.includes(id)) order.push(id);
      });
      return { tasks, order };
    }),
  upsert: (p) =>
    set((s) => {
      const prev = s.tasks[p.taskId];
      const item: TaskItem = {
        ...(prev ?? blank(p.taskId)), ...p,
        title: prev?.title || p.batchTitle || p.taskId,
        batchId: p.batchId || prev?.batchId,
        error: p.state === "error" ? p.error : undefined,
      };
      return {
        tasks: { ...s.tasks, [p.taskId]: item },
        order: prev ? s.order : [...s.order, p.taskId],
      };
    }),
  removeOne: (id) =>
    set((s) => {
      const tasks = { ...s.tasks };
      delete tasks[id];
      return { tasks, order: s.order.filter((x) => x !== id) };
    }),
  clearFinished: () =>
    set((s) => {
      const order = s.order.filter((id) => {
        const t = s.tasks[id];
        return t && t.state !== "done" && t.state !== "canceled";
      });
      const tasks: Record<string, TaskItem> = {};
      order.forEach((id) => { if (s.tasks[id]) tasks[id] = s.tasks[id]; });
      return { tasks, order };
    }),
  clearAll: () => set({ tasks: {}, order: [] }),
}));
