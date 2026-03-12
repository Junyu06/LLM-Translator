import type { AppConfig } from "../../types";

type TranslationSettingsFormProps = {
  config: AppConfig;
  languages: string[];
  onSourceLangChange: (value: string) => void;
  onTargetLangChange: (value: string) => void;
  onOutputModeChange: (value: AppConfig["output_mode"]) => void;
  onUseContextChange: (checked: boolean) => void;
  onCollapseNewlinesChange: (checked: boolean) => void;
};

export function TranslationSettingsForm({
  config,
  languages,
  onSourceLangChange,
  onTargetLangChange,
  onOutputModeChange,
  onUseContextChange,
  onCollapseNewlinesChange
}: TranslationSettingsFormProps) {
  return (
    <>
      <div className="grid compact-grid">
        <label className="field">
          <span className="field-label">Source</span>
          <select value={config.source_lang} onChange={(event) => onSourceLangChange(event.target.value)}>
            {languages.map((lang) => (
              <option key={lang} value={lang}>
                {lang}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span className="field-label">Target</span>
          <select value={config.target_lang} onChange={(event) => onTargetLangChange(event.target.value)}>
            {languages.filter((lang) => lang !== "auto").map((lang) => (
              <option key={lang} value={lang}>
                {lang}
              </option>
            ))}
          </select>
        </label>

        <label className="field">
          <span className="field-label">Output</span>
          <select
            value={config.output_mode}
            onChange={(event) => onOutputModeChange(event.target.value as AppConfig["output_mode"])}
          >
            <option value="translations_only">translations_only</option>
            <option value="interleaved">interleaved</option>
          </select>
        </label>
      </div>

      <div className="toggle-grid">
        <label className="toggle-card">
          <input type="checkbox" checked={config.use_context} onChange={(event) => onUseContextChange(event.target.checked)} />
          <span>
            <strong>Use Context</strong>
            <em>Send adjacent segment context into the prompt.</em>
          </span>
        </label>

        <label className="toggle-card">
          <input
            type="checkbox"
            checked={config.collapse_newlines}
            onChange={(event) => onCollapseNewlinesChange(event.target.checked)}
          />
          <span>
            <strong>Collapse Newlines</strong>
            <em>Reduce overly tall output blocks after rendering.</em>
          </span>
        </label>
      </div>
    </>
  );
}
