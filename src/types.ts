export type TranslationSegment = { source: string; target: string; done: boolean };

export type HistoryItem = {
  id: string;
  source: string;
  target: string;
  timestamp: number;
  segments?: TranslationSegment[];
};

export type AppConfig = {
  source_lang: string;
  target_lang: string;
  collapse_newlines: boolean;
  output_mode: "translations_only" | "interleaved";
  translation_mode: "normal" | "markdown";
  layout: "vertical" | "horizontal";
  mode: "local" | "http";
  host: string;
  model: string;
  font_size: number;
  hotkey_enabled: boolean;
  minimize_to_tray: boolean;
  theme: "light" | "dark" | "system";
  ui_lang: "en" | "zh";
};

export type TranslationRequest = {
  text: string;
  source_lang: string;
  target_lang: string;
  collapse_newlines: boolean;
  output_mode: "translations_only" | "interleaved";
  translation_mode: "normal" | "markdown";
  mode: "local" | "http";
  host: string;
  model: string;
};

export type TranslationResponse = {
  output_text: string;
  detected_source_lang: string | null;
  segments: Array<{ source: string; target: string }>;
};

// One line of the bridge's translate-stream output, plus events added by the Rust shell.
export type TranslationEvent = {
  event: "started" | "update" | "completed" | "error" | "canceled";
  output_text?: string;
  segments?: TranslationSegment[];
  completed_segments?: number;
  total_segments?: number;
  detected_source_lang?: string | null;
  code?: string;
  message?: string;
};
