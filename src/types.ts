// `kept`: shown as it is, never translated (code, blank lines). Older history
// items lack it; for them a target equal to its source means the same.
export type TranslationSegment = { source: string; target: string; done: boolean; kept?: boolean };

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
  glossary: string;
  prompt_style: PromptStyle;
  custom_prompt: string;
  // Copying twice shows the result in a small window instead of the main one.
  quick_window: boolean;
};

// A finished translation from the quick window, handed to the main window.
export type QuickResult = {
  source: string;
  output: string;
  segments: TranslationSegment[];
  detected_source_lang: string | null;
};

export type PromptStyle = "auto" | "index" | "hy" | "generic" | "custom";

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
  glossary: string;
  prompt_style: PromptStyle;
  custom_prompt: string;
  // Re-translating one paragraph: the paragraphs before it, and some randomness.
  context?: Array<{ source: string; target: string }>;
  temperature?: number;
  // The text is one block already split out: translate it without splitting again.
  as_block?: boolean;
};

export type TranslationResponse = {
  output_text: string;
  detected_source_lang: string | null;
  segments: Array<{ source: string; target: string; kept?: boolean }>;
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
