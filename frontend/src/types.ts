// ytdlp-studio:generated v1
export interface ParsedURL {
  kind: string;
  videoId: string;
  listId: string;
  canonicalUrl: string;
  ambiguous: boolean;
  isMix: boolean;
}

export interface MediaEntry {
  id: string;
  url: string;
  title: string;
  durationSec: number;
  thumbnail: string;
  index: number;
  available: boolean;
}

export interface MediaInfo {
  kind: string;
  id: string;
  title: string;
  entries: MediaEntry[] | null;
}

export interface DownloadOptions {
  mode: string;
  audioFormat: string;
  audioQuality: string;
  videoHeight: number;
  videoContainer: string;
  outputDir: string;
  nameTemplate: string;
  embedThumbnail: boolean;
  embedMetadata: boolean;
  concurrentFragments: number;
  rateLimit: string;
  cookiesBrowser: string;
}

export interface TaskProgress {
  taskId: string;
  state: string;
  percent: number;
  speedBps: number;
  etaSec: number;
  error?: string;
  filePath?: string;
}

export interface DepStatus {
  ytDlp: boolean;
  ffmpeg: boolean;
  ffprobe: boolean;
  jsRuntime: string;
  missing: string[] | null;
}
