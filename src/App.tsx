import { useEffect, useRef, useState } from "react";

import HistoryDrawer from "./components/HistoryDrawer";
import SettingsSheet, { type ModelList } from "./components/SettingsSheet";
import TranslationView from "./components/TranslationView";
import { LANGUAGES, languageName, translator, type StringKey } from "./i18n";
import { IconClipboard, IconCollapse, IconCopy, IconExpand, IconHistory, IconLock, IconSettings, IconStop, IconSwap, IconTrash, IconUnlock } from "./icons";
import {
  type DesktopBackendStatus,
  type HotkeyStatus,
  cancelTranslation,
  checkAccessibility,
  checkInputMonitoring,
  getHotkeyStatus,
  isTauriRuntime,
  listModels,
  loadInitialConfig,
  notifyFrontendReady,
  onHotkeyError,
  openPrivacySettings,
  readClipboard,
  refreshBackendStatus,
  requestAccessibility,
  requestInputMonitoring,
  saveConfig,
  startTranslationStream,
  syncHotkeyListener,
  takeTranslationEvents,
  translate,
  writeClipboardText
} from "./lib/api";
import { addHistoryItem, loadHistory, readStorage, saveHistory, writeStorage } from "./lib/history";
import type { AppConfig, HistoryItem, TranslationEvent, TranslationRequest, TranslationSegment } from "./types";
import "./styles.css";

declare const __BUILD_PLATFORM__: "windows" | "macos" | "linux";

const BUILD_PLATFORM = typeof __BUILD_PLATFORM__ === "string" ? __BUILD_PLATFORM__ : "linux";
const IS_MAC_BUILD = BUILD_PLATFORM === "macos";
const TRANSLATE_SHORTCUT = IS_MAC_BUILD ? "⌘↩" : "Ctrl+Enter";
const DOUBLE_COPY_SHORTCUT = IS_MAC_BUILD ? "⌘C ⌘C" : "Ctrl+C Ctrl+C";
const PERMISSION_AUTO_REQUEST_KEY = "translator_permission_autorequest_v1";
const POLL_INTERVAL_MS = 120;

const defaultConfig: AppConfig = {
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
  ui_lang: "en"
};

type Status = { text: string; tone: "idle" | "busy" | "error" };

const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));

const errorText = (error: unknown) => (error instanceof Error ? error.message : String(error));

export default function App() {
  const [config, setConfig] = useState<AppConfig>(defaultConfig);
  const [input, setInput] = useState("");
  const [segments, setSegments] = useState<TranslationSegment[]>([]);
  const [output, setOutput] = useState("");
  const [detectedLang, setDetectedLang] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState({ completed: 0, total: 0 });
  const [status, setStatus] = useState<Status>({ text: "", tone: "idle" });
  const [backendStatus, setBackendStatus] = useState<DesktopBackendStatus | null>(null);
  const [hotkeyStatus, setHotkeyStatus] = useState<HotkeyStatus | null>(null);
  const [permissions, setPermissions] = useState({ accessibility: true, inputMonitoring: true });
  const [showSettings, setShowSettings] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [fullscreenPanel, setFullscreenPanel] = useState<null | "input" | "output">(null);
  const [scrollLocked, setScrollLocked] = useState(false);
  const [history, setHistory] = useState<HistoryItem[]>(() => loadHistory());
  const [models, setModels] = useState<ModelList>({ models: [], error: null, loading: false });

  // Each translation gets a run id. Anything that resolves after a newer run
  // started, or after Stop/Clear, checks the id and drops its result.
  const runIdRef = useRef(0);
  const jobIdRef = useRef<number | null>(null);
  const configRef = useRef(config);
  const inputScrollRef = useRef<HTMLTextAreaElement>(null);
  const outputScrollRef = useRef<HTMLDivElement>(null);
  const syncingScrollRef = useRef<HTMLElement | null>(null);
  const statusTimerRef = useRef<number | null>(null);
  const permissionPollRef = useRef<number | null>(null);
  const captureRef = useRef<() => Promise<void>>(async () => {});

  configRef.current = config;
  const t = translator(config.ui_lang);
  const lang = (code: string) => languageName(config.ui_lang, code);

  const showStatus = (text: string, tone: Status["tone"] = "idle", clearAfterMs?: number) => {
    if (statusTimerRef.current !== null) window.clearTimeout(statusTimerRef.current);
    statusTimerRef.current = null;
    setStatus({ text, tone });
    if (clearAfterMs) {
      statusTimerRef.current = window.setTimeout(() => setStatus({ text: "", tone: "idle" }), clearAfterMs);
    }
  };

  const describeFailure = (code: string | undefined, message: string) => {
    const current = configRef.current;
    const host = current.mode === "http" && current.host.trim() ? current.host.trim() : "127.0.0.1:11434";
    const known: Record<string, string> = {
      ollama_unavailable: t("err_unreachable", { host }),
      model_not_found: t("err_model_missing", { model: current.model }),
      backend_timeout: t("err_timeout"),
      backend_stream_error: `${t("err_model_failed")}: ${message}`,
      backend_stream_incomplete: t("err_model_failed"),
      bridge_exited: t("err_process")
    };
    return (code && known[code]) || message;
  };

  // ---------- translation ----------

  const stopCurrentJob = () => {
    const jobId = jobIdRef.current;
    jobIdRef.current = null;
    if (jobId !== null) void cancelTranslation(jobId);
  };

  const applyEvent = (event: TranslationEvent) => {
    if (event.segments) setSegments(event.segments);
    if (event.output_text !== undefined) setOutput(event.output_text);
    if (event.detected_source_lang !== undefined) setDetectedLang(event.detected_source_lang);
    if (event.total_segments !== undefined) {
      setProgress({ completed: event.completed_segments ?? 0, total: event.total_segments });
    }
  };

  const followJob = async (jobId: number, runId: number, sourceText: string) => {
    while (runIdRef.current === runId) {
      let events: TranslationEvent[];
      try {
        events = await takeTranslationEvents<TranslationEvent>(jobId);
      } catch (error) {
        if (runIdRef.current !== runId) return;
        setRunning(false);
        showStatus(errorText(error), "error");
        return;
      }
      if (runIdRef.current !== runId) return;

      for (const event of events) {
        applyEvent(event);
        if (event.event === "completed") {
          jobIdRef.current = null;
          setRunning(false);
          showStatus(t("done"), "idle", 2500);
          setHistory((prev) => addHistoryItem(prev, sourceText, event.output_text ?? "", event.segments ?? []));
          return;
        }
        if (event.event === "error") {
          jobIdRef.current = null;
          setRunning(false);
          showStatus(describeFailure(event.code, event.message ?? "Translation failed"), "error");
          return;
        }
        if (event.event === "canceled") {
          jobIdRef.current = null;
          setRunning(false);
          return;
        }
      }
      await sleep(POLL_INTERVAL_MS);
    }
  };

  const runTranslation = async (text: string) => {
    if (!text.trim()) return;
    // A new request replaces whatever is still running.
    const runId = runIdRef.current + 1;
    runIdRef.current = runId;
    stopCurrentJob();

    const current = configRef.current;
    setInput(text);
    setSegments([]);
    setOutput("");
    setDetectedLang(null);
    setProgress({ completed: 0, total: 0 });
    setRunning(true);
    showStatus(t("translating"), "busy");

    const request: TranslationRequest = {
      text,
      source_lang: current.source_lang,
      target_lang: current.target_lang,
      collapse_newlines: current.collapse_newlines,
      // Side-by-side is drawn from segments, so switching views never needs a new request.
      output_mode: "translations_only",
      translation_mode: current.translation_mode,
      mode: current.mode,
      host: current.host,
      model: current.model
    };

    if (isTauriRuntime()) {
      let jobId: number;
      try {
        jobId = await startTranslationStream(request);
      } catch (error) {
        if (runIdRef.current !== runId) return;
        setRunning(false);
        showStatus(errorText(error), "error");
        return;
      }
      if (runIdRef.current !== runId) {
        void cancelTranslation(jobId);
        return;
      }
      jobIdRef.current = jobId;
      await followJob(jobId, runId, text);
      return;
    }

    // Browser development: no streaming.
    try {
      const response = await translate(request);
      if (runIdRef.current !== runId) return;
      const done = response.segments.map((segment) => ({ ...segment, done: true }));
      setSegments(done);
      setOutput(response.output_text);
      setDetectedLang(response.detected_source_lang);
      setHistory((prev) => addHistoryItem(prev, text, response.output_text, done));
      showStatus(t("done"), "idle", 2500);
    } catch (error) {
      if (runIdRef.current === runId) showStatus(errorText(error), "error");
    } finally {
      if (runIdRef.current === runId) setRunning(false);
    }
  };

  const stopTranslation = () => {
    runIdRef.current += 1;
    stopCurrentJob();
    setRunning(false);
    showStatus(t("stopped"), "idle", 2500);
  };

  const clearAll = () => {
    runIdRef.current += 1;
    stopCurrentJob();
    setRunning(false);
    setInput("");
    setSegments([]);
    setOutput("");
    setDetectedLang(null);
    showStatus("");
  };

  const openHistoryItem = (item: HistoryItem) => {
    runIdRef.current += 1;
    stopCurrentJob();
    setRunning(false);
    setInput(item.source);
    setSegments(item.segments ?? []);
    setOutput(item.target);
    setDetectedLang(null);
    showStatus("");
  };

  // Clipboard button, double-copy hotkey, tray menu and pasting an image all
  // land here. Text is used as-is; an image comes back as OCR text. Reading
  // the clipboard (and OCR) counts as part of the run, so Stop, Clear, a
  // history item or a newer capture drops a result that arrives late.
  captureRef.current = async () => {
    const runId = runIdRef.current + 1;
    runIdRef.current = runId;
    stopCurrentJob();
    // Running, so Stop and Clear work while the clipboard or OCR is read.
    setRunning(true);
    showStatus(t("reading_clipboard"), "busy");
    const giveUp = (text: string, clearAfterMs?: number) => {
      setRunning(false);
      showStatus(text, "error", clearAfterMs);
    };

    let text = "";
    let source: "text" | "image" | "empty" = "empty";
    // Right after a double copy the source app may still be writing the clipboard.
    for (let attempt = 0; attempt < 3 && source === "empty"; attempt += 1) {
      if (attempt > 0) await sleep(80);
      if (runIdRef.current !== runId) return;
      try {
        const capture = await readClipboard();
        source = capture.source;
        text = capture.text;
      } catch (error) {
        if (runIdRef.current === runId) giveUp(`${t("clipboard_error")}: ${errorText(error)}`);
        return;
      }
    }
    if (runIdRef.current !== runId) return;
    if (!text.trim()) {
      giveUp(source === "image" ? t("ocr_no_text") : t("clipboard_empty"), 4000);
      return;
    }
    await runTranslation(text);
  };

  // Pasting an image runs the same capture: OCR, then translate.
  const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const items = Array.from(e.clipboardData?.items ?? []);
    if (!items.some((item) => item.type.startsWith("image/"))) return;
    e.preventDefault();
    void captureRef.current();
  };

  // ---------- config ----------

  const updateConfig = (patch: Partial<AppConfig>) => {
    configRef.current = { ...configRef.current, ...patch };
    setConfig((prev) => ({ ...prev, ...patch }));
    if (patch.theme) document.body.setAttribute("data-theme", patch.theme);
    void saveConfig(patch).catch((error) => console.error(error));
  };

  const refreshModels = async () => {
    setModels((prev) => ({ ...prev, loading: true }));
    try {
      const names = await listModels(configRef.current);
      setModels({ models: names, error: null, loading: false });
    } catch (error) {
      setModels({ models: [], error: errorText(error), loading: false });
    }
  };

  const swapLanguages = () => {
    updateConfig({ source_lang: config.target_lang, target_lang: config.source_lang });
    if (output.trim()) {
      runIdRef.current += 1;
      stopCurrentJob();
      setRunning(false);
      setInput(output);
      setSegments([]);
      setOutput("");
    }
  };

  // ---------- permissions (macOS) ----------

  const recheckPermissions = async () => {
    const [accessibility, inputMonitoring] = await Promise.all([checkAccessibility(), checkInputMonitoring()]);
    setPermissions({ accessibility, inputMonitoring });
    if (accessibility && inputMonitoring) await syncHotkeyListener();
    return accessibility && inputMonitoring;
  };

  const startPermissionPolling = () => {
    if (permissionPollRef.current !== null) window.clearInterval(permissionPollRef.current);
    let attempts = 0;
    permissionPollRef.current = window.setInterval(async () => {
      attempts += 1;
      const granted = await recheckPermissions().catch(() => false);
      if ((granted || attempts >= 180) && permissionPollRef.current !== null) {
        window.clearInterval(permissionPollRef.current);
        permissionPollRef.current = null;
      }
    }, 1000);
  };

  const initializeMacPermissions = async () => {
    if (await recheckPermissions()) return;
    if (readStorage(PERMISSION_AUTO_REQUEST_KEY) !== "1") {
      writeStorage(PERMISSION_AUTO_REQUEST_KEY, "1");
      await requestAccessibility().catch((error) => console.error(error));
      await requestInputMonitoring().catch((error) => console.error(error));
    }
    startPermissionPolling();
  };

  // ---------- startup ----------

  // Rust calls window.__translatorTriggerClipboardTranslation() for the hotkey and tray menu.
  useEffect(() => {
    (globalThis as any).__translatorTriggerClipboardTranslation = () => {
      void captureRef.current();
    };
    return () => {
      delete (globalThis as any).__translatorTriggerClipboardTranslation;
    };
  }, []);

  useEffect(() => {
    let canceled = false;
    let unlistenHotkeyError: (() => void) | null = null;

    if (isTauriRuntime()) {
      void notifyFrontendReady().catch((error) => console.error(error));
      void onHotkeyError((message) => {
        if (!canceled) setHotkeyStatus({ state: "error", error: message });
      }).then((unlisten) => {
        if (canceled) unlisten();
        else unlistenHotkeyError = unlisten;
      });
    }

    void loadInitialConfig()
      .then(({ config: saved }) => {
        if (canceled) return;
        const merged = { ...defaultConfig, ...saved };
        configRef.current = merged;
        setConfig(merged);
        document.body.setAttribute("data-theme", merged.theme || "system");
        if (isTauriRuntime() && IS_MAC_BUILD) void initializeMacPermissions();
      })
      .catch((error) => {
        if (canceled) return;
        document.body.setAttribute("data-theme", defaultConfig.theme);
        showStatus(errorText(error), "error");
      })
      .finally(() => {
        void Promise.all([refreshBackendStatus(), getHotkeyStatus()])
          .then(([backend, hotkey]) => {
            if (canceled) return;
            setBackendStatus(backend);
            setHotkeyStatus(hotkey);
          })
          .catch((error) => console.error(error));
      });

    return () => {
      canceled = true;
      unlistenHotkeyError?.();
      if (permissionPollRef.current !== null) window.clearInterval(permissionPollRef.current);
      if (statusTimerRef.current !== null) window.clearTimeout(statusTimerRef.current);
    };
  }, []);

  useEffect(() => saveHistory(history), [history]);

  useEffect(() => {
    if (isTauriRuntime() && IS_MAC_BUILD) void syncHotkeyListener();
  }, [config.hotkey_enabled]);

  useEffect(() => {
    if (showSettings) void refreshModels();
  }, [showSettings]);

  // ---------- scroll sync ----------

  const syncScroll = (source: HTMLElement, target: HTMLElement | null) => {
    if (!scrollLocked || !target || syncingScrollRef.current === source) return;
    const sourceMax = Math.max(source.scrollHeight - source.clientHeight, 0);
    const targetMax = Math.max(target.scrollHeight - target.clientHeight, 0);
    syncingScrollRef.current = target;
    target.scrollTop = sourceMax === 0 ? 0 : (source.scrollTop / sourceMax) * targetMax;
    window.setTimeout(() => {
      if (syncingScrollRef.current === target) syncingScrollRef.current = null;
    }, 80);
  };

  // ---------- render ----------

  const bilingual = config.output_mode === "interleaved";
  const markdown = config.translation_mode === "markdown";
  const sourceLabel = config.source_lang === "auto" && detectedLang
    ? `${lang(detectedLang)} · ${t("detected")}`
    : lang(config.source_lang);
  const problems = [
    backendStatus && backendStatus.state !== "running" ? `${t("backend_problem")}: ${backendStatus.error ?? backendStatus.state}` : null,
    hotkeyStatus?.state === "error" ? `${t("hotkey_problem")}: ${hotkeyStatus.error ?? ""}` : null
  ].filter(Boolean) as string[];
  const progressRatio = progress.total ? (progress.completed / progress.total) * 100 : 0;

  const copyOutput = async () => {
    try {
      await writeClipboardText(output);
      showStatus(t("copied"), "idle", 2000);
    } catch (error) {
      showStatus(errorText(error), "error");
    }
  };

  const iconButton = (label: StringKey, onClick: () => void, icon: JSX.Element, extra?: { disabled?: boolean; active?: boolean }) => (
    <button
      className={`icon-btn${extra?.active ? " active" : ""}`}
      onClick={onClick}
      title={t(label)}
      aria-label={t(label)}
      disabled={extra?.disabled}
    >
      {icon}
    </button>
  );

  return (
    <div className="app-container" style={{ fontSize: `${config.font_size}px` }}>
      <nav className="app-nav">
        <div className="segmented-control" role="group">
          <button className={`segment-btn ${!markdown ? "active" : ""}`} onClick={() => updateConfig({ translation_mode: "normal" })}>{t("mode_normal")}</button>
          <button className={`segment-btn ${markdown ? "active" : ""}`} onClick={() => updateConfig({ translation_mode: "markdown" })} title={t("mode_markdown_desc")}>{t("mode_markdown")}</button>
        </div>

        <div className="lang-switcher">
          <select className="lang-select" value={config.source_lang} onChange={(e) => updateConfig({ source_lang: e.target.value })}>
            {LANGUAGES.map((code) => <option key={code} value={code}>{lang(code)}</option>)}
          </select>
          {iconButton("swap", swapLanguages, <IconSwap />, { disabled: config.source_lang === "auto" })}
          <select className="lang-select" value={config.target_lang} onChange={(e) => updateConfig({ target_lang: e.target.value })}>
            {LANGUAGES.filter((code) => code !== "auto").map((code) => <option key={code} value={code}>{lang(code)}</option>)}
          </select>
        </div>

        <div className="nav-right">
          <div className="segmented-control" role="group">
            <button className={`segment-btn ${!bilingual ? "active" : ""}`} onClick={() => updateConfig({ output_mode: "translations_only" })}>{t("view_translation")}</button>
            <button className={`segment-btn ${bilingual ? "active" : ""}`} onClick={() => updateConfig({ output_mode: "interleaved" })} title={t("view_bilingual_desc")}>{t("view_bilingual")}</button>
          </div>
          {iconButton("history", () => setShowHistory(true), <IconHistory />)}
          {iconButton("settings", () => setShowSettings(true), <IconSettings />)}
        </div>
      </nav>

      <main className={`main-workspace${fullscreenPanel ? " fullscreen" : ""}`}>
        <section className={`editor-panel${fullscreenPanel === "output" ? " panel-hidden" : ""}`}>
          <div className="panel-header">
            <span className="panel-label">{sourceLabel}</span>
            <div className="row-actions">
              {fullscreenPanel === "input"
                ? iconButton("exit_fullscreen", () => setFullscreenPanel(null), <IconCollapse />)
                : iconButton("fullscreen", () => setFullscreenPanel("input"), <IconExpand />)}
              {iconButton("clear", clearAll, <IconTrash />, { disabled: !input && !output && !running })}
            </div>
          </div>
          <textarea
            ref={inputScrollRef}
            className="source-text"
            placeholder={t("source_placeholder", { shortcut: TRANSLATE_SHORTCUT })}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onScroll={(e) => syncScroll(e.currentTarget, outputScrollRef.current)}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === "Enter") void runTranslation(input);
            }}
            onPaste={handlePaste}
          />
          <div className="panel-footer">
            <button className="secondary-btn" onClick={() => void captureRef.current()} title={t("from_clipboard_desc")}>
              <IconClipboard />
              <span>{t("from_clipboard")}</span>
            </button>
            {running ? (
              <button className="primary-btn stop-btn" onClick={stopTranslation}>
                <IconStop />
                <span>{t("stop")}</span>
              </button>
            ) : (
              <button className="primary-btn" disabled={!input.trim()} onClick={() => void runTranslation(input)}>
                <span>{t("translate")}</span>
                <kbd>{TRANSLATE_SHORTCUT}</kbd>
              </button>
            )}
          </div>
        </section>

        <section className={`editor-panel${fullscreenPanel === "input" ? " panel-hidden" : ""}`}>
          {running && <div className="progress-container"><div className="progress-bar" style={{ width: `${Math.max(progressRatio, 4)}%` }} /></div>}
          <div className="panel-header">
            <span className="panel-label">{lang(config.target_lang)}</span>
            <div className="row-actions">
              {iconButton(scrollLocked ? "unlock_scroll" : "lock_scroll", () => setScrollLocked(!scrollLocked), scrollLocked ? <IconLock /> : <IconUnlock />, { active: scrollLocked })}
              {fullscreenPanel === "output"
                ? iconButton("exit_fullscreen", () => setFullscreenPanel(null), <IconCollapse />)
                : iconButton("fullscreen", () => setFullscreenPanel("output"), <IconExpand />)}
              {iconButton("copy", copyOutput, <IconCopy />, { disabled: !output })}
            </div>
          </div>
          <div ref={outputScrollRef} className="output-content" onScroll={(e) => syncScroll(e.currentTarget, inputScrollRef.current)}>
            <TranslationView
              segments={segments}
              outputText={output}
              bilingual={bilingual}
              markdown={markdown}
              running={running}
              emptyHint={t("output_empty", { shortcut: DOUBLE_COPY_SHORTCUT })}
            />
          </div>
        </section>
      </main>

      <footer className="status-bar">
        <span className={`status-${status.tone}`}>{status.text}</span>
        <span className="status-right">
          {problems.map((problem) => <span key={problem} className="status-error">{problem}</span>)}
          <span>{config.model}</span>
        </span>
      </footer>

      {showSettings && (
        <SettingsSheet
          t={t}
          config={config}
          update={updateConfig}
          models={models}
          refreshModels={() => void refreshModels()}
          isMac={IS_MAC_BUILD}
          doubleCopyShortcut={DOUBLE_COPY_SHORTCUT}
          permissions={permissions}
          openPrivacySettings={(page) => void openPrivacySettings(page)}
          recheckPermissions={() => void recheckPermissions()}
          onClose={() => setShowSettings(false)}
        />
      )}

      {showHistory && (
        <HistoryDrawer
          t={t}
          history={history}
          onOpen={openHistoryItem}
          onDelete={(id) => setHistory((prev) => prev.filter((item) => item.id !== id))}
          onClear={() => setHistory([])}
          onClose={() => setShowHistory(false)}
        />
      )}
    </div>
  );
}
