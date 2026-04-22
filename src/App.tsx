import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import {
  isTauriRuntime,
  notifyFrontendReady,
  readClipboardText,
  requestAccessibility,
  requestInputMonitoring,
  runClipboardOcr,
  saveConfig,
  startTranslationStream,
  syncHotkeyListener,
  takeTranslationEvents,
  translate,
  waitForBackend,
  cancelTranslation,
  checkAccessibility,
  checkInputMonitoring,
  openPrivacySettings,
  writeClipboardText
} from "./lib/api";
import type { AppConfig, HistoryItem, TranslationRequest, TranslationResponse } from "./types";
import { IconCollapse, IconCopy, IconExpand, IconHistory, IconLock, IconMagic, IconSearch, IconSettings, IconStop, IconSwap, IconTrash, IconUnlock, IconX } from "./icons";
import "./styles.css";

// --- i18n & Lang Mapping ---
const LANG_MAP: Record<string, Record<string, string>> = {
  en: { auto: "Detect", zh: "Chinese", en: "English", ja: "Japanese", ko: "Korean", fr: "French", de: "German", es: "Spanish", ru: "Russian" },
  zh: { auto: "自动检测", zh: "中文", en: "英语", ja: "日语", ko: "韩语", fr: "法语", de: "德语", es: "西班牙语", ru: "俄语" }
};

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
    accessibility: "Accessibility",
    accessibility_desc: "Required for the double-⌘C hotkey.",
    grant_accessibility: "Grant Access",
    accessibility_granted: "Granted",
    input_monitoring: "Input Monitoring",
    input_monitoring_desc: "Required for the double-⌘C hotkey.",
    search: "Search history...",
    empty_history: "No translations found.",
    confirm_clear: "Purge all history?",
    cancel: "Cancel",
    placeholder: "Type, paste text or image...",
    internal: "Internal",
    external: "Ollama",
    light: "Light",
    dark: "Dark",
    system: "System",
    mode_normal: "Normal",
    mode_markdown: "Markdown",
    mode_markdown_desc: "Preserve Markdown structure during translation."
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
    accessibility: "辅助功能",
    accessibility_desc: "双击 ⌘C 快捷键需要此权限。",
    grant_accessibility: "授予权限",
    accessibility_granted: "已授权",
    input_monitoring: "输入监控",
    input_monitoring_desc: "双击 ⌘C 快捷键需要此权限。",
    search: "搜索历史...",
    empty_history: "暂无历史记录。",
    confirm_clear: "确定清空所有记录？",
    cancel: "取消",
    placeholder: "输入、粘贴文本或图片...",
    internal: "内置引擎",
    external: "Ollama",
    light: "亮色",
    dark: "暗色",
    system: "跟随系统",
    mode_normal: "常规",
    mode_markdown: "Markdown",
    mode_markdown_desc: "翻译时保留 Markdown 结构并渲染。"
  }
};

// --- Types ---
interface ExtendedConfig extends AppConfig {}
const LANGUAGES = ["auto", "zh", "en", "ja", "ko", "fr", "de", "es", "ru"];

const cleanText = (text: string | undefined | null) => {
  if (!text) return "";
  return text.toString().replace(/\n/g, " ");
};

const defaultConfig: ExtendedConfig = {
  source_lang: "auto",
  target_lang: "zh",
  use_context: false,
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
  ui_lang: "en"
};

const PERMISSION_AUTO_REQUEST_KEY = "translator_permission_autorequest_v1";

const Toggle = ({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) => (
  <label className="switch"><input type="checkbox" checked={checked} onChange={e => onChange(e.target.checked)} /><span className="slider"></span></label>
);

export default function App() {
  const [config, setConfig] = useState<ExtendedConfig>(defaultConfig);
  const [input, setInput] = useState("");
  const [output, setOutput] = useState("");
  const [status, setStatus] = useState("Initializing...");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [progressRatio, setProgressRatio] = useState(0);
  const [showSettings, setShowSettings] = useState(false);
  const [isSizingFont, setIsSizingFont] = useState(false);
  const [segments, setSegments] = useState<Array<{ source: string; target: string }>>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [confirmClear, setConfirmClear] = useState(false);
  const [fullscreenPanel, setFullscreenPanel] = useState<null | "input" | "output">(null);
  const [scrollLocked, setScrollLocked] = useState(false);
  const scrollLockedRef = useRef(false);
  const inputScrollRef = useRef<HTMLTextAreaElement>(null);
  const outputScrollRef = useRef<HTMLDivElement>(null);
  const syncedScrollTargetRef = useRef<HTMLElement | null>(null);
  const scrollSyncReleaseRef = useRef<number | null>(null);
  const [accessibilityGranted, setAccessibilityGranted] = useState(true);
  const [inputMonitoringGranted, setInputMonitoringGranted] = useState(true);
  const [history, setHistory] = useState<HistoryItem[]>(() => {
    const saved = localStorage.getItem("translator_history_v2");
    return saved ? JSON.parse(saved) : [];
  });
  
  const currentJobIdRef = useRef<number | null>(null);
  const historyListRef = useRef<HTMLDivElement>(null);
  const historyScrollRef = useRef(0);
  const permissionPollRef = useRef<number | null>(null);
  const runTranslationRef = useRef<(text: string) => Promise<void>>(async () => {});
  const captureClipboardIntoInputRef = useRef<(prefilledText?: string, autoTranslate?: boolean) => Promise<void>>(async () => {});
  const t = (key: keyof typeof I18N.en) => I18N[config.ui_lang || "en"][key];
  const langName = (code: string) => LANG_MAP[config.ui_lang || "en"][code] || code.toUpperCase();

  const stopPermissionPolling = () => {
    if (permissionPollRef.current !== null) {
      window.clearInterval(permissionPollRef.current);
      permissionPollRef.current = null;
    }
  };

  const startPermissionPolling = (initialAccessibility: boolean, initialInputMonitoring: boolean) => {
    stopPermissionPolling();

    let lastAccessibility = initialAccessibility;
    let lastInputMonitoring = initialInputMonitoring;
    let syncedHotkey = false;
    let attempts = 0;

    const poll = async () => {
      attempts += 1;
      try {
        const [ax, im] = await Promise.all([checkAccessibility(), checkInputMonitoring()]);
        setAccessibilityGranted(ax);
        setInputMonitoringGranted(im);

        if (ax && im && !syncedHotkey) {
          syncedHotkey = true;
          await syncHotkeyListener();
        }

        lastAccessibility = ax;
        lastInputMonitoring = im;

        if ((ax && im) || attempts >= 180) {
          stopPermissionPolling();
        }
      } catch (error) {
        console.error(error);
        if (attempts >= 180) {
          stopPermissionPolling();
        }
      }
    };

    void poll();
    permissionPollRef.current = window.setInterval(() => {
      void poll();
    }, 1000);
  };

  const initializeMacPermissions = async () => {
    if (!isTauriRuntime()) return;

    const [ax, im] = await Promise.all([checkAccessibility(), checkInputMonitoring()]);
    setAccessibilityGranted(ax);
    setInputMonitoringGranted(im);

    if (ax && im) {
      await syncHotkeyListener();
      return;
    }

    const hasAutoRequested = localStorage.getItem(PERMISSION_AUTO_REQUEST_KEY) === "1";
    if (!hasAutoRequested) {
      localStorage.setItem(PERMISSION_AUTO_REQUEST_KEY, "1");

      if (!ax) {
        try {
          await requestAccessibility();
        } catch (error) {
          console.error(error);
        }
      }

      if (!im) {
        try {
          await requestInputMonitoring();
        } catch (error) {
          console.error(error);
        }
      }
    }

    startPermissionPolling(ax, im);
  };

  // Hotkey bridge: Rust evals window.__translatorTriggerClipboardTranslation(text)
  useEffect(() => {
    (globalThis as any).__translatorTriggerClipboardTranslation = (text?: string) => {
      void captureClipboardIntoInputRef.current(text, true);
    };
    return () => { delete (globalThis as any).__translatorTriggerClipboardTranslation; };
  }, []);

  useEffect(() => {
    void waitForBackend().then(({ config: savedConfig }) => {
      const merged = { ...defaultConfig, ...savedConfig };
      setConfig(merged);
      setStatus(I18N[merged.ui_lang || "en"]["ready"]);
      document.body.setAttribute("data-theme", merged.theme || "system");
      if (isTauriRuntime()) {
        void notifyFrontendReady();
        void initializeMacPermissions();
      }
    }).catch((err) => setStatus(`Error: ${err.message}`));
    return () => {
      stopPermissionPolling();
    };
  }, []);

  useEffect(() => { localStorage.setItem("translator_history_v2", JSON.stringify(history)); }, [history]);

  const releaseScrollSyncLock = () => {
    if (scrollSyncReleaseRef.current !== null) {
      window.clearTimeout(scrollSyncReleaseRef.current);
      scrollSyncReleaseRef.current = null;
    }
    syncedScrollTargetRef.current = null;
  };

  const handleScrollSync = (source: HTMLElement, target: HTMLElement) => {
    if (!scrollLockedRef.current) return;
    if (syncedScrollTargetRef.current === source) return;

    const sourceMaxScroll = Math.max(source.scrollHeight - source.clientHeight, 0);
    const targetMaxScroll = Math.max(target.scrollHeight - target.clientHeight, 0);
    const progress = sourceMaxScroll === 0 ? 0 : source.scrollTop / sourceMaxScroll;
    const nextTargetScrollTop = progress * targetMaxScroll;

    syncedScrollTargetRef.current = target;
    target.scrollTop = nextTargetScrollTop;

    if (scrollSyncReleaseRef.current !== null) {
      window.clearTimeout(scrollSyncReleaseRef.current);
    }
    scrollSyncReleaseRef.current = window.setTimeout(() => {
      syncedScrollTargetRef.current = null;
      scrollSyncReleaseRef.current = null;
    }, 80);
  };

  useEffect(() => {
    if (isTauriRuntime()) void syncHotkeyListener();
  }, [config.hotkey_enabled]);

  useEffect(() => releaseScrollSyncLock, []);

  useEffect(() => {
    if (showHistory && historyListRef.current) {
      historyListRef.current.scrollTop = historyScrollRef.current;
    }
  }, [showHistory]);

  const closeHistory = () => {
    if (historyListRef.current) historyScrollRef.current = historyListRef.current.scrollTop;
    setShowHistory(false);
    setConfirmClear(false);
  };

  const addToHistory = (source: string, target: string) => {
    if (!source.trim() || !target.trim()) return;
    const newItem: HistoryItem = { id: Math.random().toString(36).substring(2, 9), source: source.trim(), target: target.trim(), timestamp: Date.now() };
    setHistory(prev => [newItem, ...prev.filter(i => i.source !== source.trim()).slice(0, 99)]);
  };

  const runTranslation = async (text: string) => {
    if (!text.trim() || isSubmitting) return;
    setInput(text); setOutput(""); setSegments([]); setIsSubmitting(true); setProgressRatio(0);
    const request: TranslationRequest = {
      text,
      source_lang: config.source_lang,
      target_lang: config.target_lang,
      use_context: config.use_context,
      collapse_newlines: config.collapse_newlines,
      output_mode: config.output_mode,
      translation_mode: config.translation_mode,
      mode: config.mode,
      host: config.host,
      model: config.model,
    };
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
      setOutput(resp.output_text); 
      if (resp.segments) setSegments(resp.segments);
      addToHistory(text, resp.output_text); 
      setStatus(t("done"));
    } catch (err: any) { setStatus(`Error: ${err.message}`); } finally { setIsSubmitting(false); setProgressRatio(100); }
  };

  runTranslationRef.current = runTranslation;
  captureClipboardIntoInputRef.current = async (prefilledText?: string, autoTranslate = false) => {
    let clipboardText = prefilledText ?? "";
    if (!clipboardText) {
      for (let attempt = 0; attempt < 6; attempt += 1) {
        clipboardText = await readClipboardText().catch(() => "");
        if (clipboardText) break;
        await new Promise((resolve) => window.setTimeout(resolve, 50));
      }
    }
    setInput(clipboardText);
    setOutput("");
    setSegments([]);
    setStatus(t("ready"));

    if (autoTranslate && clipboardText) {
      await runTranslationRef.current(clipboardText);
    }
  };
  const pollProgress = async (jobId: number, sourceText: string) => {
    let finalOutput = "";
    let doneSegs: { source: string; target: string }[] = [];
    while (currentJobIdRef.current === jobId) {
      const events = await takeTranslationEvents<any>(jobId);
      for (const ev of events) {
        if (ev.event === "update" || ev.event === "completed") {
          if (ev.output_text) { setOutput(ev.output_text); finalOutput = ev.output_text; }
          if (ev.total_segments) setProgressRatio((ev.completed_segments / ev.total_segments) * 100);
          // Real-time bilingual segment tracking
          if (ev.active_segment_source) {
            const status = ev.segment_status;
            if (status === "completed" || status === "passthrough") {
              doneSegs = [...doneSegs, { source: ev.active_segment_source, target: ev.active_segment_target }];
              setSegments(doneSegs);
            } else if (status === "streaming") {
              setSegments([...doneSegs, { source: ev.active_segment_source, target: ev.active_segment_target }]);
            }
          }
        }
        if (ev.event === "completed") { setIsSubmitting(false); currentJobIdRef.current = null; setStatus(t("done")); addToHistory(sourceText, finalOutput); }
        if (ev.event === "error" || ev.event === "canceled") { setIsSubmitting(false); currentJobIdRef.current = null; setStatus(ev.message || "Failed"); }
      }
      await new Promise(r => setTimeout(r, 150));
    }
  };

  const stopTranslation = () => {
    const jobId = currentJobIdRef.current;
    currentJobIdRef.current = null;
    setIsSubmitting(false);
    setStatus("Stopped");
    if (jobId !== null) void cancelTranslation(jobId);
  };

  const updateConfig = (patch: Partial<ExtendedConfig>) => {
    setConfig(prev => ({ ...prev, ...patch }));
    if (patch.theme) document.body.setAttribute("data-theme", patch.theme);
    void saveConfig(patch as any).catch((error) => {
      console.error(error);
    });
  };

  const filteredHistory = (history || []).filter(i => {
    if (!i || !i.source || !i.target) return false;
    const term = (searchTerm || "").toLowerCase();
    return i.source.toLowerCase().includes(term) || i.target.toLowerCase().includes(term);
  });

  const handlePaste = async (e: React.ClipboardEvent) => {
    const items = e.clipboardData.items;
    let hasImage = false;
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.indexOf("image") !== -1) {
        hasImage = true;
        break;
      }
    }
    if (hasImage) {
      e.preventDefault();
      setStatus("OCR...");
      try {
        const text = await runClipboardOcr();
        if (text) runTranslation(text);
        else setStatus("No text found in image");
      } catch (err: any) {
        setStatus(`OCR Error: ${err.message}`);
      }
    }
  };

  return (
    <div className="app-container" style={{ fontSize: `${config.font_size}px` }}>
      <nav className="app-nav">
        <div className="nav-brand">{t("title")}</div>
        <div className="lang-switcher">
          <select className="lang-select" value={config.source_lang} onChange={e => updateConfig({ source_lang: e.target.value })}>
            {LANGUAGES.map(l => <option key={l} value={l}>{langName(l)}</option>)}
          </select>
          <button className="icon-btn" onClick={() => { updateConfig({ source_lang: config.target_lang, target_lang: config.source_lang }); setInput(output); setOutput(input); setSegments([]); }} disabled={config.source_lang === "auto"}><IconSwap /></button>
          <select className="lang-select" value={config.target_lang} onChange={e => updateConfig({ target_lang: e.target.value })}>
            {LANGUAGES.filter(l => l !== "auto").map(l => <option key={l} value={l}>{langName(l)}</option>)}
          </select>
        </div>
        <div className="nav-right">
          <div className="mode-switcher">
            <button className={`mode-btn ${config.translation_mode === "normal" ? "active" : ""}`} onClick={() => updateConfig({ translation_mode: "normal" })} title={t("mode_normal")}>{t("mode_normal")}</button>
            <button className={`mode-btn ${config.translation_mode === "markdown" ? "active" : ""}`} onClick={() => updateConfig({ translation_mode: "markdown" })} title={t("mode_markdown_desc")}>{t("mode_markdown")}</button>
          </div>
          <div className="nav-actions">
            <button className="icon-btn" onClick={() => setShowHistory(true)} title={t("history")}><IconHistory /></button>
            <button className="icon-btn" onClick={async () => { setShowSettings(true); const [ax, im] = await Promise.all([checkAccessibility(), checkInputMonitoring()]); setAccessibilityGranted(ax); setInputMonitoringGranted(im); }} title={t("settings")}><IconSettings /></button>
          </div>
        </div>
      </nav>

      <main className={`main-workspace${fullscreenPanel ? " fullscreen" : ""}`}>
        <section className={`editor-panel${fullscreenPanel === "output" ? " panel-hidden" : ""}`}>
          <div className="panel-header">
            <span className="panel-label">{t("source")}</span>
            <div style={{ display: "flex", gap: 4 }}>
              <button className="icon-btn" onClick={() => setFullscreenPanel(fullscreenPanel === "input" ? null : "input")} title={fullscreenPanel === "input" ? "Exit fullscreen" : "Fullscreen"}>{fullscreenPanel === "input" ? <IconCollapse /> : <IconExpand />}</button>
              <button className="icon-btn" onClick={() => { setInput(""); setOutput(""); }}><IconTrash /></button>
            </div>
          </div>
          <div className="editor-content">
            <textarea ref={inputScrollRef} placeholder={t("placeholder")} value={input} onChange={e => setInput(e.target.value)} onScroll={e => { if (outputScrollRef.current) handleScrollSync(e.currentTarget, outputScrollRef.current); }} onKeyDown={e => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") runTranslation(input); }} onPaste={async (e) => { const items = e.clipboardData?.items; if (!items) return; for (let i = 0; i < items.length; i++) { if (items[i].type.startsWith("image/")) { e.preventDefault(); setStatus("OCR..."); try { const text = await runClipboardOcr(); if (text) runTranslation(text); else setStatus("No text"); } catch (err: any) { setStatus(`OCR Error: ${err.message}`); } return; } } }} />
          </div>
        </section>
        <section className={`editor-panel${fullscreenPanel === "input" ? " panel-hidden" : ""}`}>
          {isSubmitting && <div className="progress-container"><div className="progress-bar" style={{ width: `${progressRatio}%` }} /></div>}
          <div className="panel-header">
            <span className="panel-label">{t("translation")}</span>
            <div style={{ display: "flex", gap: 4 }}>
              <button className="icon-btn" onMouseDown={e => e.preventDefault()} onClick={() => { const next = !scrollLockedRef.current; scrollLockedRef.current = next; setScrollLocked(next); }} title={scrollLocked ? "Unlock scroll" : "Lock scroll sync"} style={scrollLocked ? { color: "var(--bg-accent)" } : undefined}>{scrollLocked ? <IconLock /> : <IconUnlock />}</button>
              <button className="icon-btn" onClick={() => setFullscreenPanel(fullscreenPanel === "output" ? null : "output")} title={fullscreenPanel === "output" ? "Exit fullscreen" : "Fullscreen"}>{fullscreenPanel === "output" ? <IconCollapse /> : <IconExpand />}</button>
              <button className="icon-btn" onClick={async () => { try { await writeClipboardText(output); setStatus(t("copied")); setTimeout(() => setStatus(t("done")), 2000); } catch (err: any) { setStatus(`Copy Error: ${err.message}`); } }} disabled={!output}><IconCopy /></button>
            </div>
          </div>
          <div ref={outputScrollRef} className="editor-content output-content" onScroll={e => { if (inputScrollRef.current) handleScrollSync(e.currentTarget, inputScrollRef.current); }}>
            {config.output_mode === "interleaved" && segments.length > 0 ? (
              <div className="bilingual-viewer">
                {segments.map((seg, i) => (
                  <div key={i} className="bilingual-segment">
                    <div className="segment-source">{seg.source}</div>
                    <div className="segment-target">
                      {config.translation_mode === "markdown" ? (
                        <div className="markdown-body"><ReactMarkdown>{seg.target}</ReactMarkdown></div>
                      ) : seg.target}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              config.translation_mode === "markdown" && output ? (
                <div className="markdown-body"><ReactMarkdown>{output}</ReactMarkdown></div>
              ) : (
                output || <span style={{ color: "var(--fg-subtle)" }}>{t("ready")}...</span>
              )
            )}
          </div>
        </section>
      </main>

      <div className="floating-toolbar">
        <button className="icon-btn" onClick={() => { void captureClipboardIntoInputRef.current(undefined, true); }}><IconMagic /></button>
        <div style={{ width: 1, alignSelf: "stretch", background: "var(--border-medium)", margin: "4px 0" }} />
        {isSubmitting ? (
          <button className="primary-btn stop-btn" onClick={stopTranslation}>
            <IconStop />
            <span>Stop</span>
          </button>
        ) : (
          <button className="primary-btn" disabled={!input.trim()} onClick={() => runTranslation(input)}>
            Translate
            <span style={{ fontSize: "0.7rem", opacity: 0.6, marginLeft: 4 }}>⌘↵</span>
          </button>
        )}
      </div>

      <footer className="status-bar">
        <span>{status}</span>
        <span>{config.model} • {config.mode === "local" ? t("internal") : t("external")}</span>
      </footer>

      {showSettings && (
        <div className="overlay-mask" onClick={() => setShowSettings(false)} style={isSizingFont ? { backdropFilter: "none", WebkitBackdropFilter: "none" } : undefined}>
          <div className="settings-card" onClick={e => e.stopPropagation()} style={isSizingFont ? { opacity: 0.25, transition: "opacity 0.1s" } : undefined}>
            <div className="settings-header">
              <h2 className="settings-title">{t("settings")}</h2>
              <button className="icon-btn" onClick={() => setShowSettings(false)}><IconX /></button>
            </div>
            
            <div className="settings-body">
              <div className="settings-section">
                <div className="section-label">{t("engine")}</div>
                <div className="settings-list">
                  <div className="settings-row">
                    <div className="settings-info"><div className="settings-name">{t("inference")}</div></div>
                    <div className="segmented-control">
                      <button className={`segment-btn ${config.mode === "local" ? "active" : ""}`} onClick={() => updateConfig({ mode: "local" })}>{t("internal")}</button>
                      <button className={`segment-btn ${config.mode === "http" ? "active" : ""}`} onClick={() => updateConfig({ mode: "http" })}>{t("external")}</button>
                    </div>
                  </div>
                  <div className="settings-row">
                    <div className="settings-info"><div className="settings-name">{t("model")}</div><div className="settings-desc">{t("model_desc")}</div></div>
                    <div className="settings-input-wrapper"><input className="settings-input" value={config.model} onChange={e => updateConfig({ model: e.target.value })} /></div>
                  </div>
                  {config.mode === "http" && (
                    <div className="settings-row">
                      <div className="settings-info"><div className="settings-name">{t("host")}</div><div className="settings-desc">{t("host_desc")}</div></div>
                      <div className="settings-input-wrapper"><input className="settings-input" value={config.host} onChange={e => updateConfig({ host: e.target.value })} /></div>
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
                      <input type="range" min="12" max="26" value={config.font_size} onChange={e => updateConfig({ font_size: parseInt(e.target.value) })} onPointerDown={() => setIsSizingFont(true)} onPointerUp={() => setIsSizingFont(false)} style={{ width: 100, accentColor: "var(--bg-accent)" }} />
                      <span style={{ fontSize: "0.85rem", fontWeight: 800 }}>{config.font_size}</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="settings-section">
                <div className="section-label">{t("features")}</div>
                <div className="settings-list">
                  <div className="settings-row">
                    <div className="settings-info">
                      <div className="settings-name">{t("accessibility")}</div>
                      <div className="settings-desc">{t("accessibility_desc")}</div>
                    </div>
                    {accessibilityGranted
                      ? <span style={{ fontSize: "0.8rem", color: "var(--fg-muted)", fontWeight: 600 }}>{t("accessibility_granted")} ✓</span>
                      : <div style={{ display: "flex", gap: 6 }}>
                          <button className="secondary-btn-sm" onClick={() => openPrivacySettings("accessibility")}>{t("grant_accessibility")}</button>
                          <button className="secondary-btn-sm" onClick={async () => { await syncHotkeyListener(); setAccessibilityGranted(await checkAccessibility()); }}>{config.ui_lang === "zh" ? "重试" : "Retry"}</button>
                        </div>
                    }
                  </div>
                  <div className="settings-row">
                    <div className="settings-info">
                      <div className="settings-name">{t("input_monitoring")}</div>
                      <div className="settings-desc">{t("input_monitoring_desc")}</div>
                    </div>
                    {inputMonitoringGranted
                      ? <span style={{ fontSize: "0.8rem", color: "var(--fg-muted)", fontWeight: 600 }}>{t("accessibility_granted")} ✓</span>
                      : <div style={{ display: "flex", gap: 6 }}>
                          <button className="secondary-btn-sm" onClick={() => openPrivacySettings("input_monitoring")}>{t("grant_accessibility")}</button>
                          <button className="secondary-btn-sm" onClick={async () => { await syncHotkeyListener(); setInputMonitoringGranted(await checkInputMonitoring()); }}>{config.ui_lang === "zh" ? "重试" : "Retry"}</button>
                        </div>
                    }
                  </div>
                  <div className="settings-row">
                    <div className="settings-info"><div className="settings-name">{t("bilingual")}</div><div className="settings-desc">{t("bilingual_desc")}</div></div>
                    <Toggle checked={config.output_mode === "interleaved"} onChange={v => updateConfig({ output_mode: v ? "interleaved" : "translations_only" })} />
                  </div>
                  <div className="settings-row">
                    <div className="settings-info"><div className="settings-name">{t("context")}</div><div className="settings-desc">{t("context_desc")}</div></div>
                    <Toggle checked={config.use_context} onChange={v => updateConfig({ use_context: v })} />
                  </div>
                </div>
              </div>
            </div>

            <div className="settings-footer">
              <button className="primary-btn" style={{ width: "100%" }} onClick={() => setShowSettings(false)}>{t("done")}</button>
            </div>
          </div>
        </div>
      )}

      {/* --- HISTORY --- */}
      {showHistory && (
        <div className="overlay-mask" onClick={closeHistory} style={{ justifyContent: "flex-end" }}>
          <div className="drawer-card" onClick={e => e.stopPropagation()}>
            <div className="drawer-header">
              <div className="drawer-top-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                <h2 className="settings-title" style={{ margin: 0 }}>{t("history")}</h2>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                   {confirmClear ? (
                     <>
                       <button className="secondary-btn-sm danger-btn" onClick={() => { setHistory([]); setConfirmClear(false); }}>{t("confirm_clear")}</button>
                       <button className="secondary-btn-sm" onClick={() => setConfirmClear(false)}>{t("cancel")}</button>
                     </>
                   ) : (
                     <button className="secondary-btn-sm" onClick={() => setConfirmClear(true)}>
                       <IconTrash /> {t("clear")}
                     </button>
                   )}
                   <button className="icon-btn" onClick={closeHistory}><IconX /></button>
                </div>
              </div>
              <div className="history-search-container">
                <span className="search-icon"><IconSearch /></span>
                <input className="history-search-input" placeholder={t("search")} value={searchTerm} onChange={e => setSearchTerm(e.target.value)} />
              </div>
            </div>
            <div className="history-list" ref={historyListRef}>
              {filteredHistory.length === 0 ? (
                <div style={{ color: "var(--fg-subtle)", textAlign: "center", marginTop: 40, fontSize: "0.875rem" }}>{searchTerm ? "No matches." : t("empty_history")}</div>
              ) : (
                filteredHistory.map(item => (
                  <div key={item.id} className="history-item" onClick={() => { setInput(item.source); setOutput(item.target); closeHistory(); }}>
                    <div className="history-content">
                      <div className="history-source">{cleanText(item.source)}</div>
                      <div className="history-target">{cleanText(item.target)}</div>
                    </div>
                    <div className="history-actions">
                      <button className="history-delete-btn" onClick={(e) => { e.stopPropagation(); setHistory(h => h.filter(i => i.id !== item.id)); }}><IconTrash /></button>
                    </div>
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
