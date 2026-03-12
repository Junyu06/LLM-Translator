import type { AppConfig } from "../../types";

type AppSettingsPanelProps = {
  config: AppConfig;
  onModeChange: (value: AppConfig["mode"]) => void;
  onModelChange: (value: string) => void;
  onHostChange: (value: string) => void;
  onHotkeyEnabledChange: (checked: boolean) => void;
  onMinimizeToTrayChange: (checked: boolean) => void;
};

export function AppSettingsPanel({
  config,
  onModeChange,
  onModelChange,
  onHostChange,
  onHotkeyEnabledChange,
  onMinimizeToTrayChange
}: AppSettingsPanelProps) {
  return (
    <section className="panel page-card page-surface settings-page">
      <div className="page-header-block">
        <p className="section-kicker">Settings</p>
        <h2 className="page-title">Application settings</h2>
      </div>

      <div className="settings-section">
        <div className="settings-section-copy">
          <h3>Backend</h3>
          <p className="helper-text">Persistent translation backend options used by the desktop app.</p>
        </div>
        <div className="settings-form">
          <div className="grid compact-grid">
            <label className="field">
              <span className="field-label">Backend</span>
              <select value={config.mode} onChange={(event) => onModeChange(event.target.value as AppConfig["mode"])}>
                <option value="local">local</option>
                <option value="http">http</option>
              </select>
            </label>
          </div>

          <label className="field">
            <span className="field-label">Model</span>
            <input value={config.model} onChange={(event) => onModelChange(event.target.value)} />
          </label>

          <label className="field">
            <span className="field-label">Host</span>
            <input value={config.host} onChange={(event) => onHostChange(event.target.value)} />
          </label>
        </div>
      </div>

      <div className="settings-section">
        <div className="settings-section-copy">
          <h3>Desktop behavior</h3>
          <p className="helper-text">Application-level behavior that should not clutter the main translation workflow.</p>
        </div>
        <div className="toggle-grid">
          <label className="toggle-card">
            <input type="checkbox" checked={config.hotkey_enabled} onChange={(event) => onHotkeyEnabledChange(event.target.checked)} />
            <span>
              <strong>Double-Copy Hotkey</strong>
              <em>Use Cmd+C Cmd+C on macOS or Ctrl+C Ctrl+C on Windows.</em>
            </span>
          </label>

          <label className="toggle-card">
            <input
              type="checkbox"
              checked={config.minimize_to_tray}
              onChange={(event) => onMinimizeToTrayChange(event.target.checked)}
            />
            <span>
              <strong>Minimize To Tray</strong>
              <em>Closing the desktop window hides it instead of quitting the app.</em>
            </span>
          </label>
        </div>
      </div>
    </section>
  );
}
