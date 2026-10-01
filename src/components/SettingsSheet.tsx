import { useEffect, useState } from "react";

import type { StringKey } from "../i18n";
import type { AppConfig, PromptStyle } from "../types";
import { IconX } from "../icons";

type T = (key: StringKey, values?: Record<string, string | number>) => string;

export type ModelList = { models: string[]; error: string | null; loading: boolean };

type Props = {
  t: T;
  config: AppConfig;
  update: (patch: Partial<AppConfig>) => void;
  models: ModelList;
  refreshModels: () => void;
  isMac: boolean;
  doubleCopyShortcut: string;
  permissions: { accessibility: boolean; inputMonitoring: boolean };
  openPrivacySettings: (page: "accessibility" | "input_monitoring") => void;
  recheckPermissions: () => void;
  onClose: () => void;
};

const Toggle = ({ checked, onChange, label }: { checked: boolean; onChange: (value: boolean) => void; label: string }) => (
  <label className="switch">
    <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} aria-label={label} />
    <span className="slider" />
  </label>
);

// Same rule as core/prompt.py detect_family.
const familyOf = (model: string) => {
  const name = model.trim().toLowerCase().replace(/_/g, "-");
  if (name.includes("index-translate") || name.includes("indexteam")) return "Index-Translate";
  if (name.includes("hy-mt") || name.includes("hymt") || name.includes("hunyuan-mt")) return "Hy-MT";
  return null;
};

// A text box that saves when it loses focus, not on every keystroke.
function DraftArea({ value, onCommit, placeholder, rows }: { value: string; onCommit: (value: string) => void; placeholder?: string; rows: number }) {
  const [draft, setDraft] = useState(value);
  useEffect(() => setDraft(value), [value]);
  return (
    <textarea
      className="settings-textarea"
      value={draft}
      rows={rows}
      placeholder={placeholder}
      spellCheck={false}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => { if (draft !== value) onCommit(draft); }}
    />
  );
}

function Segmented<V extends string>({ value, options, onChange }: { value: V; options: Array<[V, string]>; onChange: (value: V) => void }) {
  return (
    <div className="segmented-control">
      {options.map(([option, label]) => (
        <button key={option} className={`segment-btn ${value === option ? "active" : ""}`} onClick={() => onChange(option)}>{label}</button>
      ))}
    </div>
  );
}

export default function SettingsSheet(props: Props) {
  const { t, config, update, models } = props;
  const [sizing, setSizing] = useState(false);
  const host = config.mode === "http" ? config.host : "";

  const modelNote = models.error
    ? t("model_desc_unreachable", { error: models.error })
    : models.models.length === 0
      ? ""
      : models.models.includes(config.model)
        ? t("model_desc_count", { count: models.models.length })
        : t("model_desc_missing");

  const permissionRow = (name: StringKey, granted: boolean, page: "accessibility" | "input_monitoring") => (
    <div className="settings-row">
      <div className="settings-info">
        <div className="settings-name">{t(name)}</div>
        <div className="settings-desc">{t("permission_desc", { shortcut: props.doubleCopyShortcut })}</div>
      </div>
      {granted ? (
        <span className="settings-state">{t("granted")}</span>
      ) : (
        <div className="row-actions">
          <button className="secondary-btn-sm" onClick={() => props.openPrivacySettings(page)}>{t("grant")}</button>
          <button className="secondary-btn-sm" onClick={props.recheckPermissions}>{t("retry")}</button>
        </div>
      )}
    </div>
  );

  return (
    <div className="overlay-mask" onClick={props.onClose} style={sizing ? { backdropFilter: "none", WebkitBackdropFilter: "none" } : undefined}>
      <div className="settings-card" onClick={(e) => e.stopPropagation()} style={sizing ? { opacity: 0.25 } : undefined}>
        <div className="settings-header">
          <h2 className="settings-title">{t("settings")}</h2>
          <button className="icon-btn" onClick={props.onClose} title={t("close")}><IconX /></button>
        </div>

        <div className="settings-body">
          <section className="settings-section">
            <div className="section-label">{t("settings_translation")}</div>
            <div className="settings-row">
              <div className="settings-info">
                <div className="settings-name">{t("server")}</div>
                <div className="settings-desc">{t("server_desc")}</div>
              </div>
              <input
                className="settings-input"
                value={host}
                placeholder={t("server_placeholder")}
                spellCheck={false}
                onChange={(e) => update({ host: e.target.value, mode: e.target.value.trim() ? "http" : "local" })}
                onBlur={props.refreshModels}
              />
            </div>
            <div className="settings-row">
              <div className="settings-info">
                <div className="settings-name">{t("model")}</div>
                {modelNote && <div className={`settings-desc ${models.error || !models.models.includes(config.model) ? "warn" : ""}`}>{modelNote}</div>}
              </div>
              <div className="row-actions">
                {models.models.length > 0 ? (
                  <select className="settings-input settings-select" value={config.model} onChange={(e) => update({ model: e.target.value })}>
                    {!models.models.includes(config.model) && <option value={config.model}>{config.model}</option>}
                    {models.models.map((name) => <option key={name} value={name}>{name}</option>)}
                  </select>
                ) : (
                  <input
                    className="settings-input"
                    value={config.model}
                    spellCheck={false}
                    onChange={(e) => update({ model: e.target.value })}
                  />
                )}
                <button className="secondary-btn-sm" onClick={props.refreshModels} disabled={models.loading}>{t("refresh_models")}</button>
              </div>
            </div>
          </section>


          <section className="settings-section">
            <div className="section-label">{t("settings_prompt")}</div>
            <div className="settings-row">
              <div className="settings-info">
                <div className="settings-name">{t("prompt")}</div>
                <div className="settings-desc">
                  {config.prompt_style === "auto"
                    ? t("prompt_desc_auto", { family: familyOf(config.model) ?? t("prompt_generic") })
                    : config.prompt_style === "custom" ? t("prompt_desc_custom") : t("prompt_desc_fixed")}
                </div>
              </div>
              <select className="settings-input settings-select narrow" value={config.prompt_style} onChange={(e) => update({ prompt_style: e.target.value as PromptStyle })}>
                <option value="auto">{t("prompt_auto")}</option>
                <option value="index">Index-Translate</option>
                <option value="hy">Hy-MT</option>
                <option value="generic">{t("prompt_generic")}</option>
                <option value="custom">{t("prompt_custom")}</option>
              </select>
            </div>
            {config.prompt_style === "custom" && (
              <div className="settings-stack">
                <div className="settings-info">
                  <div className="settings-name">{t("custom_prompt")}</div>
                  <div className="settings-desc">{t("custom_prompt_desc")}</div>
                </div>
                <DraftArea
                  value={config.custom_prompt}
                  rows={4}
                  placeholder={"Translate the following text into {target_lang}. Output only the translation.\n\n{text}"}
                  onCommit={(custom_prompt) => update({ custom_prompt })}
                />
              </div>
            )}
            <div className="settings-stack">
              <div className="settings-info">
                <div className="settings-name">{t("glossary")}</div>
                <div className="settings-desc">{t("glossary_desc")}</div>
              </div>
              <DraftArea
                value={config.glossary}
                rows={5}
                placeholder={"medium setting = medium 思考档位\nhubctl = hubctl"}
                onCommit={(glossary) => update({ glossary })}
              />
            </div>
          </section>

          <section className="settings-section">
            <div className="section-label">{t("settings_hotkey")}</div>
            <div className="settings-row">
              <div className="settings-info">
                <div className="settings-name">{t("hotkey")}</div>
                <div className="settings-desc">{t("hotkey_desc", { shortcut: props.doubleCopyShortcut })}</div>
              </div>
              <Toggle checked={config.hotkey_enabled} onChange={(value) => update({ hotkey_enabled: value })} label={t("hotkey")} />
            </div>
            {props.isMac && permissionRow("accessibility", props.permissions.accessibility, "accessibility")}
            {props.isMac && permissionRow("input_monitoring", props.permissions.inputMonitoring, "input_monitoring")}
          </section>

          <section className="settings-section">
            <div className="section-label">{t("settings_appearance")}</div>
            <div className="settings-row">
              <div className="settings-name">{t("theme")}</div>
              <Segmented value={config.theme} onChange={(theme) => update({ theme })} options={[["light", t("light")], ["dark", t("dark")], ["system", t("system")]]} />
            </div>
            <div className="settings-row">
              <div className="settings-name">{t("ui_lang")}</div>
              <Segmented value={config.ui_lang} onChange={(ui_lang) => update({ ui_lang })} options={[["en", "English"], ["zh", "简体中文"]]} />
            </div>
            <div className="settings-row">
              <div className="settings-name">{t("font_size")}</div>
              <div className="row-actions">
                <input
                  type="range"
                  min="12"
                  max="26"
                  value={config.font_size}
                  onChange={(e) => update({ font_size: parseInt(e.target.value, 10) })}
                  onPointerDown={() => setSizing(true)}
                  onPointerUp={() => setSizing(false)}
                  className="font-slider"
                />
                <span className="settings-state">{config.font_size}</span>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
