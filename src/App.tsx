import { FormEvent, useEffect, useState } from "react";

import { saveConfig, translate, waitForBackend } from "./lib/api";
import type { AppConfig, TranslationResponse } from "./types";
import "./styles.css";

const defaultConfig: AppConfig = {
  source_lang: "auto",
  target_lang: "en",
  use_context: false,
  collapse_newlines: false,
  output_mode: "translations_only",
  layout: "vertical",
  mode: "local",
  host: "http://127.0.0.1:11434",
  model: "demonbyron/HY-MT1.5-1.8B"
};

const languages = ["auto", "zh", "en", "ja", "ko", "fr", "de", "es", "ru"];

export default function App() {
  const [config, setConfig] = useState<AppConfig>(defaultConfig);
  const [input, setInput] = useState("");
  const [output, setOutput] = useState("");
  const [status, setStatus] = useState("Starting desktop backend...");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [lastResponse, setLastResponse] = useState<TranslationResponse | null>(null);
  const [isBackendReady, setIsBackendReady] = useState(false);

  useEffect(() => {
    void waitForBackend()
      .then(({ config: savedConfig, desktopStatus }) => {
        setConfig(savedConfig);
        setIsBackendReady(true);
        setStatus(desktopStatus?.python ? `Backend ready · ${desktopStatus.python}` : "Backend ready");
      })
      .catch((error: Error) => {
        setStatus(`Backend unavailable: ${error.message}`);
      });
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!input.trim()) {
      setStatus("Nothing to translate.");
      return;
    }

    setIsSubmitting(true);
    setStatus("Translating...");
    try {
      const response = await translate({
        text: input,
        source_lang: config.source_lang,
        target_lang: config.target_lang,
        use_context: config.use_context,
        collapse_newlines: config.collapse_newlines,
        output_mode: config.output_mode,
        mode: config.mode,
        host: config.host,
        model: config.model
      });
      setOutput(response.output_text);
      setLastResponse(response);
      setStatus("Done.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Translation failed.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function updateConfig<K extends keyof AppConfig>(key: K, value: AppConfig[K]) {
    const next = { ...config, [key]: value };
    setConfig(next);
    try {
      await saveConfig({ [key]: value });
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Saving config failed.");
    }
  }

  function swapLanguages() {
    if (config.source_lang === "auto") {
      return;
    }
    const next = {
      ...config,
      source_lang: config.target_lang,
      target_lang: config.source_lang
    };
    setConfig(next);
    void saveConfig({
      source_lang: next.source_lang,
      target_lang: next.target_lang
    });
  }

  return (
    <main className="shell">
      <header className="masthead">
        <div>
          <p className="eyebrow">Local Desktop Translator</p>
          <h1>Single UI, Python brain, Tauri shell</h1>
        </div>
        <div className={`status-pill ${isBackendReady ? "ready" : "pending"}`}>{status}</div>
      </header>

      <section className="workspace">
        <form className="panel controls" onSubmit={handleSubmit}>
          <div className="panel-heading">
            <div>
              <p className="section-kicker">Control Deck</p>
              <h2>Translation settings</h2>
            </div>
            <button
              className="ghost"
              type="button"
              onClick={swapLanguages}
              disabled={config.source_lang === "auto"}
            >
              Swap languages
            </button>
          </div>

          <div className="grid compact-grid">
            <label className="field">
              <span className="field-label">Source</span>
              <select
                value={config.source_lang}
                onChange={(event) => void updateConfig("source_lang", event.target.value)}
              >
                {languages.map((lang) => (
                  <option key={lang} value={lang}>
                    {lang}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              <span className="field-label">Target</span>
              <select
                value={config.target_lang}
                onChange={(event) => void updateConfig("target_lang", event.target.value)}
              >
                {languages.filter((lang) => lang !== "auto").map((lang) => (
                  <option key={lang} value={lang}>
                    {lang}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              <span className="field-label">Backend</span>
              <select
                value={config.mode}
                onChange={(event) => void updateConfig("mode", event.target.value as AppConfig["mode"])}
              >
                <option value="local">local</option>
                <option value="http">http</option>
              </select>
            </label>

            <label className="field">
              <span className="field-label">Output</span>
              <select
                value={config.output_mode}
                onChange={(event) =>
                  void updateConfig("output_mode", event.target.value as AppConfig["output_mode"])
                }
              >
                <option value="translations_only">translations_only</option>
                <option value="interleaved">interleaved</option>
              </select>
            </label>
          </div>

          <label className="field">
            <span className="field-label">Model</span>
            <input value={config.model} onChange={(event) => void updateConfig("model", event.target.value)} />
          </label>

          <label className="field">
            <span className="field-label">Host</span>
            <input value={config.host} onChange={(event) => void updateConfig("host", event.target.value)} />
          </label>

          <div className="toggle-grid">
            <label className="toggle-card">
              <input
                type="checkbox"
                checked={config.use_context}
                onChange={(event) => void updateConfig("use_context", event.target.checked)}
              />
              <span>
                <strong>Use Context</strong>
                <em>Send adjacent segment context into the prompt.</em>
              </span>
            </label>

            <label className="toggle-card">
              <input
                type="checkbox"
                checked={config.collapse_newlines}
                onChange={(event) => void updateConfig("collapse_newlines", event.target.checked)}
              />
              <span>
                <strong>Collapse Newlines</strong>
                <em>Reduce overly tall output blocks after rendering.</em>
              </span>
            </label>
          </div>

          <label className="field">
            <span className="field-label">Input</span>
            <textarea value={input} onChange={(event) => setInput(event.target.value)} rows={12} />
          </label>

          <div className="actions">
            <button className="primary" type="submit" disabled={isSubmitting || !isBackendReady}>
              {isSubmitting ? "Translating..." : "Translate"}
            </button>
            <span className="helper-text">Backend is invoked through the bundled Python bridge.</span>
          </div>
        </form>

        <section className="panel output">
          <div className="output-header">
            <div>
              <p className="section-kicker">Output</p>
              <h2>Rendered translation</h2>
            </div>
            <span className="output-meta">
              {lastResponse?.detected_source_lang ? `Detected: ${lastResponse.detected_source_lang}` : "Awaiting input"}
            </span>
          </div>
          <pre>{output || "Translation result will appear here."}</pre>
        </section>
      </section>
    </main>
  );
}
