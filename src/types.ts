export type AppConfig = {
  source_lang: string;
  target_lang: string;
  use_context: boolean;
  collapse_newlines: boolean;
  output_mode: "translations_only" | "interleaved";
  layout: "vertical" | "horizontal";
  mode: "local" | "http";
  host: string;
  model: string;
};

export type TranslationRequest = {
  text: string;
  source_lang: string;
  target_lang: string;
  use_context: boolean;
  collapse_newlines: boolean;
  output_mode: "translations_only" | "interleaved";
  mode: "local" | "http";
  host: string;
  model: string;
};

export type TranslationResponse = {
  output_text: string;
  detected_source_lang: string | null;
  segments: Array<{ source: string; target: string }>;
};

