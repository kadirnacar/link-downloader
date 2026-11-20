// ytdlp-studio:types v4 — tek kaynak: Wails bindings
// Elle tip tanımı YOKTUR. Drift imkânsızdır.

export type {
  AppSettings,
  DownloadOptions,
  MediaEntry,
  MediaInfo,
  ParsedURL,
} from "../bindings/ytdlp-studio/internal/model/models";

export type {
  BatchInfo,
  BatchProgress,
  DepStatus,
  LogLine,
  SubtitleInfo,
  SubtitleTrack,
  TaskProgress,
} from "../bindings/ytdlp-studio/services/models";

export type Tab = "analyze" | "queue" | "settings" | "logs" | "about";
