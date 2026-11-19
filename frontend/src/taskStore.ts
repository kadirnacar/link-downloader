// ytdlp-studio:generated v1
// ytdlp-studio:taskstore v1
import { create } from "zustand";
import type { MediaEntry, TaskProgress } from "./types";

export interface TaskItem extends TaskProgress {
  title: string;
}

interface TaskState {
  tasks: Record<string, TaskItem>;
  order: string[];
  addMany: (ids: string[], entries: MediaEntry[], batchId?: string) => void;
  upsert: (p: TaskProgress) => void;
  clearFinished: () => void;
}

export const useTasks = create<TaskState>((set) => ({
  tasks: {},
  order: [],
  addMany: (ids, entries, batchId) =>
    set((s) => {
      const tasks = { ...s.tasks };
      const order = [...s.order];
      ids.forEach((id, i) => {
        const e = entries[i];
        tasks[id] = {
          taskId: id,
          title: e ? e.title : id,
          state: "queued",
          percent: 0,
          speedBps: 0,
          etaSec: 0,
          batchId,
        };
        order.push(id);
      });
      return { tasks, order };
    }),
  upsert: (p) =>
    set((s) => {
      const prev = s.tasks[p.taskId];
      const base: TaskItem =
        prev ??
        {
          taskId: p.taskId,
          title: "",
          state: "queued",
          percent: 0,
          speedBps: 0,
          etaSec: 0,
        };
      const item: TaskItem = {
        ...base,
        ...p,
        error: p.state === "error" ? p.error : undefined,
      };
      const order = prev ? s.order : [...s.order, p.taskId];
      return { tasks: { ...s.tasks, [p.taskId]: item }, order };
    }),
  clearFinished: () =>
    set((s) => {
      const order = s.order.filter((id) => {
        const t = s.tasks[id];
        return t && t.state !== "done" && t.state !== "canceled";
      });
      const tasks: Record<string, TaskItem> = {};
      order.forEach((id) => {
        const t = s.tasks[id];
        if (t) tasks[id] = t;
      });
      return { tasks, order };
    }),
}));
