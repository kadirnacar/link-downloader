// ytdlp-studio:generated v1
// ytdlp-studio:store v2
import { create } from "zustand";
import type { BatchProgress, DepStatus, DownloadOptions, MediaInfo, ParsedURL } from "./types";

export const DEFAULT_OPTIONS: DownloadOptions = {
  mode: "audio",
  audioFormat: "mp3",
  audioQuality: "0",
  videoHeight: 1080,
  videoContainer: "mp4",
  outputDir: "",
  nameTemplate: "%(playlist_index)03d - %(title)s.%(ext)s",
  embedThumbnail: true,
  embedMetadata: true,
  concurrentFragments: 4,
  rateLimit: "",
  cookiesBrowser: "",
};

interface AppState {
  url: string;
  parsed?: ParsedURL;
  info?: MediaInfo;
  scope: "video" | "playlist";
  selected: Set<string>;
  options: DownloadOptions;
  analyzing: boolean;
  installing: boolean;
  error?: string;
  notice?: string;
  deps?: DepStatus;
  tab: "analyze" | "queue";
  batches: Record<string, BatchProgress>;
  set: (p: Partial<AppState>) => void;
  upsertBatch: (b: BatchProgress) => void;
}

export const useStore = create<AppState>((set) => ({
  url: "",
  scope: "video",
  selected: new Set<string>(),
  options: DEFAULT_OPTIONS,
  analyzing: false,
  installing: false,
  tab: "analyze",
  batches: {},
  set: (p) => set(p),
  upsertBatch: (b) =>
    set((s) => ({ batches: { ...s.batches, [b.batchId]: b } })),
}));
