import type { AppConfig, TranslationRequest } from "../types";

export const defaultConfig: AppConfig = {
  source_lang: "auto",
  target_lang: "zh",
  collapse_newlines: false,
  output_mode: "translations_only",
  translation_mode: "normal",
  layout: "vertical",
  mode: "local",
  host: "http://127.0.0.1:11434",
  model: "demonbyron/HY-MT1.5-1.8B",
  font_size: 14,
  hotkey_enabled: true,
  minimize_to_tray: true,
  theme: "system",
  ui_lang: "en",
  glossary: "",
  prompt_style: "auto",
  custom_prompt: "",
  quick_window: true
};

export const requestFor = (text: string, config: AppConfig): TranslationRequest => ({
  text,
  source_lang: config.source_lang,
  target_lang: config.target_lang,
  collapse_newlines: config.collapse_newlines,
  // Side-by-side is drawn from segments, so switching views never needs a new request.
  output_mode: "translations_only",
  translation_mode: config.translation_mode,
  mode: config.mode,
  host: config.host,
  model: config.model,
  glossary: config.glossary,
  prompt_style: config.prompt_style,
  custom_prompt: config.custom_prompt
});
