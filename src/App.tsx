import { ClipboardEvent, FormEvent, useEffect, useRef, useState } from "react";
import {
  cancelTranslation,
  isTauriRuntime,
  readClipboardText,
  runClipboardOcr,
  saveConfig,
  showMainWindow,
  startTranslationStream,
  syncHotkeyListener,
  takeTranslationEvents,
  translate,
  waitForBackend,
  writeClipboardText
} from "./lib/api";
import type { AppConfig, TranslationRequest, TranslationResponse } from "./types";
import "./styles.css";

// --- Icons ---
const IconSwap = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="m7 16 3-3-3-3"/><path d="m17 8-3 3 3 3"/><path d="M3 12h7"/><path d="M14 12h7"/></svg>;
const IconCopy = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>;
const IconTrash = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1-0 2 1 2 2v2"/></svg>;
const IconMagic = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg>;
const IconSettings = () => <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>;
const IconX = () => <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>;
const IconHistory = () => <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/></svg>;
const IconSearch = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>;

// --- i18n ---
const I18N = {
  en: {
    title: "Translator",
    source: "Source",
    translation: "Translation",
    ready: "Ready",
    done: "Done",
    copied: "Copied",
    clear: "Clear All",
    settings: "Preferences",
    history: "History",
    engine: "AI Engine",
    inference: "Inference Core",
    model: "Model Name",
    model_desc: "The specific LLM to use for translation.",
    host: "Server Host",
    host_desc: "Endpoint for the external service.",
    style: "Interface & Style",
    appearance: "Appearance",
    font_size: "Font Size",
    ui_lang: "UI Language",
    features: "Capabilities",
    bilingual: "Side-by-Side View",
    bilingual_desc: "Show original and translated text together.",
    context: "Smart Context",
    context_desc: "Reference surroundings for coherence.",
    hotkey: "Quick Translate",
    hotkey_desc: "Trigger on double Copy (⌘C C).",
    search: "Search history...",
    empty_history: "No translations found.",
    confirm_clear: "Purge all history?",
    placeholder: "Type or paste text here...",
    internal: "Internal",
    external: "Ollama",
    light: "Light",
    dark: "Dark",
    system: "System"
  },
  zh: {
    title: "翻译器",
    source: "原文",
    translation: "译文",
    ready: "就绪",
    done: "完成",
    copied: "已复制",
    clear: "清空全部",
    settings: "偏好设置",
    history: "历史记录",
    engine: "AI 引擎",
    inference: "推理核心",
    model: "模型名称",
    model_desc: "用于翻译的具体大语言模型。",
    host: "服务器地址",
    host_desc: "外部服务的 API 端点。",
    style: "界面与样式",
    appearance: "外观主题",
    font_size: "字体大小",
    ui_lang: "界面语言",
    features: "功能特性",
    bilingual: "对照模式",
    bilingual_desc: "同时显示原文和译文。",
    context: "智能上下文",
    context_desc: "参考上下文信息提升连贯性。",
    hotkey: "快速翻译",
    hotkey_desc: "双击 ⌘C 即可触发翻译。",
    search: "搜索历史...",
    empty_history: "暂无历史记录。",
    confirm_clear: "确定清空所有记录？",
    placeholder: "在此输入或粘贴文本...",
    internal: "内置引擎",
    external: "Ollama",
    light: "亮色",
    dark: "暗色",
    system: "跟随系统"
  }
};

// --- Types ---
type HistoryItem = { id: string; source: string; target: string; timestamp: number };

interface ExtendedConfig extends AppConfig {
  theme?: "light" | "dark" | "system";
  ui_lang?: "en" | "zh";
}

const LANGUAGES = ["auto", "zh", "en", "ja", "ko", "fr", "de", "es", "ru"];
const defaultConfig: ExtendedConfig = {
  source_lang: "auto",
  target_lang: "zh",
  use_context: false,
  collapse_newlines: false,
  output_mode: "translations_only",
  layout: "vertical",
  mode: "local",
  host: "http://127.0.0.1:11434",
  model: "demonbyron/HY-MT1.5-1.8B",
  font_size: 14,
  hotkey_enabled: true,
  minimize_to_tray: true,
  theme: "system",
  ui_lang: "en"
};

const Toggle = ({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) => (
  <label className="switch">
    <input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} />
    <span className="slider"></span>
  </label>
);

export default function App() {
  const [config, setConfig] = useState<ExtendedConfig>(defaultConfig);
  const [input, setInput] = useState("");
  const [output, setOutput] = useState("");
  const [status, setStatus] = useState("Initializing...");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [progressRatio, setProgressRatio] = useState(0);
  const [showSettings, setShowSettings] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [history, setHistory] = useState<HistoryItem[]>(() => {
    const saved = localStorage.getItem("translator_history_v2");
    return saved ? JSON.parse(saved) : [];
  });
  
  const currentJobIdRef = useRef<number | null>(null);
  const t = (key: keyof typeof I18N.en) => I18N[config.ui_lang || "en"][key];

  useEffect(() => {
    void waitForBackend()
      .then(({ config: savedConfig }) => {
        const merged = { ...defaultConfig, ...savedConfig };
        setConfig(merged);
        setStatus(t("ready"));
        document.body.setAttribute("data-theme", merged.theme || "system");
      })
      .catch((err) => setStatus(`Error: ${err.message}`));
  }, []);

  useEffect(() => { localStorage.setItem("translator_history_v2", JSON.stringify(history)); }, [history]);

  const addToHistory = (source: string, target: string) => {
    if (!source.trim() || !target.trim()) return;
    const newItem: HistoryItem = { id: Math.random().toString(36).substring(2, 9), source: source.trim(), target: target.trim(), timestamp: Date.now() };
    setHistory(prev => [newItem, ...prev.filter(i => i.source !== source.trim()).slice(0, 99)]);
  };

  const runTranslation = async (text: string) => {
    if (!text.trim() || isSubmitting) return;
    setInput(text); setOutput(""); setIsSubmitting(true); setProgressRatio(0);
    const request: TranslationRequest = { text, ...config };
    if (isTauriRuntime()) {
      try {
        const jobId = await startTranslationStream(request);
        currentJobIdRef.current = jobId;
        pollProgress(jobId, text);
        return;
      } catch (err) { console.error(err); }
    }
    try {
      const resp = await translate(request);
      setOutput(resp.output_text); addToHistory(text, resp.output_text); setStatus(t("done"));
    } catch (err: any) { setStatus(`Error: ${err.message}`); } finally { setIsSubmitting(false); setProgressRatio(100); }
  };

  const pollProgress = async (jobId: number, sourceText: string) => {
    let finalOutput = "";
    while (currentJobIdRef.current === jobId) {
      const events = await takeTranslationEvents<any>(jobId);
      for (const ev of events) {
        if (ev.event === "update" || ev.event === "completed") {
          if (ev.output_text) { setOutput(ev.output_text); finalOutput = ev.output_text; }
          if (ev.total_segments) setProgressRatio((ev.completed_segments / ev.total_segments) * 100);
        }
        if (ev.event === "completed") { setIsSubmitting(false); currentJobIdRef.current = null; setStatus(t("done")); addToHistory(sourceText, finalOutput); }
        if (ev.event === "error" || ev.event === "canceled") { setIsSubmitting(false); currentJobIdRef.current = null; setStatus(ev.message || "Failed"); }
      }
      await new Promise(r => setTimeout(r, 150));
    }
  };

  const updateConfig = async (patch: Partial<ExtendedConfig>) => {
    const next = { ...config, ...patch };
    setConfig(next);
    if (patch.theme) document.body.setAttribute("data-theme", patch.theme);
    await saveConfig(patch as any);
  };

  const filteredHistory = history.filter(i => i.source.toLowerCase().includes(searchTerm.toLowerCase()) || i.target.toLowerCase().includes(searchTerm.toLowerCase()));

  return (
    <div className="app-container" style={{ fontSize: `${config.font_size}px` }}>
      <nav className="app-nav">
        <div className="nav-brand">{t("title")}</div>
        <div className="lang-switcher">
          <select className="lang-select" value={config.source_lang} onChange={e => updateConfig({ source_lang: e.target.value })}>
            {LANGUAGES.map(l => <option key={l} value={l}>{l.toUpperCase()}</option>)}
          </select>
          <button className="icon-btn" onClick={() => updateConfig({ source_lang: config.target_lang, target_lang: config.source_lang })} disabled={config.source_lang === "auto"}><IconSwap /></button>
          <select className="lang-select" value={config.target_lang} onChange={e => updateConfig({ target_lang: e.target.value })}>
            {LANGUAGES.filter(l => l !== "auto").map(l => <option key={l} value={l}>{l.toUpperCase()}</option>)}
          </select>
        </div>
        <div className="nav-actions">
          <button className="icon-btn" onClick={() => setShowHistory(true)} title={t("history")}><IconHistory /></button>
          <button className="icon-btn" onClick={() => setShowSettings(true)} title={t("settings")}><IconSettings /></button>
        </div>
      </nav>

      <main className="main-workspace">
        <section className="editor-panel">
          <div className="panel-header">
            <span className="panel-label">{t("source")}</span>
            <button className="icon-btn" onClick={() => { setInput(""); setOutput(""); }}><IconTrash /></button>
          </div>
          <div className="editor-content">
            <textarea placeholder={t("placeholder")} value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") runTranslation(input); }} />
          </div>
        </section>
        <section className="editor-panel">
          {isSubmitting && <div className="progress-container"><div className="progress-bar" style={{ width: `${progressRatio}%` }} /></div>}
          <div className="panel-header">
            <span className="panel-label">{t("translation")}</span>
            <button className="icon-btn" onClick={async () => { await writeClipboardText(output); setStatus(t("copied")); setTimeout(() => setStatus(t("done")), 2000); }} disabled={!output}><IconCopy /></button>
          </div>
          <div className="editor-content output-content">
            {output || <span style={{ color: "var(--fg-subtle)" }}>{t("ready")}...</span>}
          </div>
        </section>
      </main>

      <div className="floating-toolbar">
        <button className="icon-btn" onClick={async () => { setStatus("OCR..."); const text = await runClipboardOcr(); if (text) runTranslation(text); else setStatus("No text"); }}><IconMagic /></button>
        <div style={{ width: 1, background: "var(--border-medium)", margin: "4px 0" }} />
        <button className="primary-btn" disabled={isSubmitting || !input.trim()} onClick={() => runTranslation(input)}>
          {isSubmitting ? "Translating..." : "Translate"}
          <span style={{ fontSize: "0.7rem", opacity: 0.6, marginLeft: 4 }}>⌘↵</span>
        </button>
      </div>

      <footer className="status-bar">
        <span>{status}</span>
        <span>{config.model} • {config.mode === "local" ? t("internal") : t("external")}</span>
      </footer>

      {showSettings && (
        <div className="overlay-mask" onClick={() => setShowSettings(false)}>
          <div className="settings-card" onClick={e => e.stopPropagation()}>
            <div className="settings-header">
              <h2 className="settings-title">{t("settings")}</h2>
              <button className="icon-btn" onClick={() => setShowSettings(false)}><IconX /></button>
            </div>
            
            <div className="settings-section">
              <div className="section-label">{t("engine")}</div>
              <div className="settings-list">
                <div className="settings-row">
                  <div className="settings-info"><div className="settings-name">{t("inference")}</div></div>
                  <div className="segmented-control">
                    <button className={`segment-btn ${config.mode === "local" ? "active" : ""}`} onClick={() => updateConfig({ mode: "local" })}>{t("internal")}</button>
                    <button className={`segment-btn ${config.mode === "ollama" ? "active" : ""}`} onClick={() => updateConfig({ mode: "ollama" })}>{t("external")}</button>
                  </div>
                </div>
                <div className="settings-row">
                  <div className="settings-info">
                    <div className="settings-name">{t("model")}</div>
                    <div className="settings-desc">{t("model_desc")}</div>
                  </div>
                  <div className="settings-input-wrapper">
                    <input className="settings-input" value={config.model} onChange={e => updateConfig({ model: e.target.value })} />
                  </div>
                </div>
                {config.mode === "ollama" && (
                  <div className="settings-row">
                    <div className="settings-info">
                      <div className="settings-name">{t("host")}</div>
                      <div className="settings-desc">{t("host_desc")}</div>
                    </div>
                    <div className="settings-input-wrapper">
                      <input className="settings-input" value={config.host} onChange={e => updateConfig({ host: e.target.value })} />
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="settings-section">
              <div className="section-label">{t("style")}</div>
              <div className="settings-list">
                <div className="settings-row">
                  <div className="settings-info"><div className="settings-name">{t("appearance")}</div></div>
                  <div className="segmented-control">
                    <button className={`segment-btn ${config.theme === "light" ? "active" : ""}`} onClick={() => updateConfig({ theme: "light" })}>{t("light")}</button>
                    <button className={`segment-btn ${config.theme === "dark" ? "active" : ""}`} onClick={() => updateConfig({ theme: "dark" })}>{t("dark")}</button>
                    <button className={`segment-btn ${config.theme === "system" ? "active" : ""}`} onClick={() => updateConfig({ theme: "system" })}>{t("system")}</button>
                  </div>
                </div>
                <div className="settings-row">
                  <div className="settings-info"><div className="settings-name">{t("ui_lang")}</div></div>
                  <div className="segmented-control">
                    <button className={`segment-btn ${config.ui_lang === "en" ? "active" : ""}`} onClick={() => updateConfig({ ui_lang: "en" })}>English</button>
                    <button className={`segment-btn ${config.ui_lang === "zh" ? "active" : ""}`} onClick={() => updateConfig({ ui_lang: "zh" })}>简体中文</button>
                  </div>
                </div>
                <div className="settings-row">
                  <div className="settings-info"><div className="settings-name">{t("font_size")}</div></div>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <input type="range" min="12" max="26" value={config.font_size} onChange={e => updateConfig({ font_size: parseInt(e.target.value) })} style={{ width: 100, accentColor: "var(--bg-accent)" }} />
                    <span style={{ fontSize: "0.85rem", fontWeight: 800 }}>{config.font_size}</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="settings-section">
              <div className="section-label">{t("features")}</div>
              <div className="settings-list">
                <div className="settings-row">
                  <div className="settings-info"><div className="settings-name">{t("bilingual")}</div><div className="settings-desc">{t("bilingual_desc")}</div></div>
                  <Toggle checked={config.output_mode === "bilingual"} onChange={v => updateConfig({ output_mode: v ? "bilingual" : "translations_only" })} />
                </div>
                <div className="settings-row">
                  <div className="settings-info"><div className="settings-name">{t("context")}</div><div className="settings-desc">{t("context_desc")}</div></div>
                  <Toggle checked={config.use_context} onChange={v => updateConfig({ use_context: v })} />
                </div>
              </div>
            </div>

            <button className="primary-btn" style={{ width: "100%", justifyContent: "center" }} onClick={() => setShowSettings(false)}>{t("done")}</button>
          </div>
        </div>
      )}

      {/* --- HISTORY --- */}
      {showHistory && (
        <div className="overlay-mask" onClick={() => setShowHistory(false)} style={{ justifyContent: "flex-end" }}>
          <div className="drawer-card" onClick={e => e.stopPropagation()}>
            <div className="drawer-header">
              <div className="drawer-top-row">
                <h2 className="settings-title">{t("history")}</h2>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                   <button className="danger-text" onClick={() => { if(confirm(t("confirm_clear"))) setHistory([]); }}>{t("clear")}</button>
                   <button className="icon-btn" onClick={() => setShowHistory(false)}><IconX /></button>
                </div>
              </div>
              <div className="history-search-container">
                <span className="search-icon"><IconSearch /></span>
                <input className="history-search-input" placeholder={t("search")} value={searchTerm} onChange={e => setSearchTerm(e.target.value)} />
              </div>
            </div>
            <div className="history-list">
              {filteredHistory.length === 0 ? (
                <div style={{ color: "var(--fg-subtle)", textAlign: "center", marginTop: 40, fontSize: "0.875rem" }}>{searchTerm ? "No matches." : t("empty_history")}</div>
              ) : (
                filteredHistory.map(item => (
                  <div key={item.id} className="history-item" onClick={() => { setInput(item.source); setOutput(item.target); setShowHistory(false); }}>
                    <div className="history-content">
                      <div className="history-source">{item.source}</div>
                      <div className="history-target">{item.target}</div>
                    </div>
                    <button className="history-delete-btn" onClick={(e) => { e.stopPropagation(); setHistory(h => h.filter(i => i.id !== item.id)); }}><IconTrash /></button>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
