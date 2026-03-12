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
import { AppShell } from "./components/layout/AppShell";
import { ContextPanel } from "./components/layout/ContextPanel";
import { Sidebar, type AppView } from "./components/layout/Sidebar";
import { StatusBar } from "./components/layout/StatusBar";
import { TopBar } from "./components/layout/TopBar";
import { HistoryPage } from "./components/pages/HistoryPage";
import { HomePage } from "./components/pages/HomePage";
import { ResourcesPage } from "./components/pages/ResourcesPage";
import { SettingsPage } from "./components/pages/SettingsPage";
import { WorkPage } from "./components/pages/WorkPage";
import { AppSettingsPanel } from "./components/settings/AppSettingsPanel";
import { InputEditor } from "./components/translation/InputEditor";
import { OutputPanel } from "./components/translation/OutputPanel";
import { TranslationControls } from "./components/translation/TranslationControls";
import { TranslationProgressSummary } from "./components/translation/TranslationProgressSummary";
import { TranslationSettingsForm } from "./components/translation/TranslationSettingsForm";
import type { AppConfig, TranslationRequest, TranslationResponse } from "./types";
import "./styles.css";

declare global {
  interface Window {
    __translatorTriggerClipboardTranslation?: (text?: string) => void;
  }
}

const defaultConfig: AppConfig = {
  source_lang: "auto",
  target_lang: "en",
  use_context: false,
  collapse_newlines: false,
  output_mode: "translations_only",
  layout: "vertical",
  mode: "local",
  host: "http://127.0.0.1:11434",
  model: "demonbyron/HY-MT1.5-1.8B",
  font_size: 14,
  hotkey_enabled: true,
  minimize_to_tray: true
};

const languages = ["auto", "zh", "en", "ja", "ko", "fr", "de", "es", "ru"];
const ENABLE_TAURI_STREAMING = true;

type TranslationProgressEvent = {
  event: "started" | "update" | "completed" | "canceled" | "error";
  job_id: number;
  output_text?: string;
  completed_segments?: number;
  total_segments?: number;
  detected_source_lang?: string | null;
  partial?: boolean;
  response?: TranslationResponse;
  message?: string;
  active_segment_index?: number | null;
  active_segment_source?: string | null;
  active_segment_target?: string;
  segment_status?: "queued" | "streaming" | "completed" | "passthrough";
};

type ProgressState = {
  totalSegments: number;
  completedSegments: number;
  activeSegmentIndex: number | null;
  activeSegmentSource: string;
  activeSegmentTarget: string;
  segmentStatus: string;
  partial: boolean;
};

const defaultProgressState: ProgressState = {
  totalSegments: 0,
  completedSegments: 0,
  activeSegmentIndex: null,
  activeSegmentSource: "",
  activeSegmentTarget: "",
  segmentStatus: "idle",
  partial: false
};

function segmentStatusLabel(progress: ProgressState) {
  if (!ENABLE_TAURI_STREAMING && isTauriRuntime()) {
    return "Blocking mode";
  }
  if (progress.segmentStatus === "streaming") {
    return "Streaming current segment";
  }
  if (progress.segmentStatus === "completed") {
    return "Segment finalized";
  }
  if (progress.segmentStatus === "passthrough") {
    return "Blank line passthrough";
  }
  if (progress.segmentStatus === "queued") {
    return "Queued";
  }
  return "Idle";
}

function compactPreview(text: string, fallback = "No active segment yet.") {
  const normalized = text.replace(/\s+/g, " ").trim();
  if (!normalized) {
    if (!ENABLE_TAURI_STREAMING && isTauriRuntime()) {
      return "Desktop streaming is temporarily disabled. Full translation will appear when ready.";
    }
    return fallback;
  }
  return normalized.length > 160 ? `${normalized.slice(0, 157)}...` : normalized;
}

async function readClipboardTextWithRetry(attempts = 4, delayMs = 120) {
  let lastText = "";
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const text = await readClipboardText();
    lastText = text;
    if (text.trim()) {
      return text;
    }
    if (attempt < attempts - 1) {
      await new Promise((resolve) => window.setTimeout(resolve, delayMs));
    }
  }
  return lastText;
}

export default function App() {
  const [config, setConfig] = useState<AppConfig>(defaultConfig);
  const [input, setInput] = useState("");
  const [output, setOutput] = useState("");
  const [status, setStatus] = useState("Starting desktop backend...");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [lastResponse, setLastResponse] = useState<TranslationResponse | null>(null);
  const [isBackendReady, setIsBackendReady] = useState(false);
  const [activeView, setActiveView] = useState<AppView>("work");
  const [isContextOpen, setIsContextOpen] = useState(true);
  const [progress, setProgress] = useState<ProgressState>(defaultProgressState);
  const currentJobIdRef = useRef<number | null>(null);
  const configRef = useRef<AppConfig>(defaultConfig);
  const progressRef = useRef<ProgressState>(defaultProgressState);
  const activeRequestTextRef = useRef("");
  const streamProducedOutputRef = useRef(false);
  const fallbackAttemptedRef = useRef(false);
  const firstProgressTimeoutRef = useRef<number | null>(null);
  const translationListenersReadyRef = useRef<Promise<void>>(Promise.resolve());
  const resolveTranslationListenersReadyRef = useRef<(() => void) | null>(null);
  const translateClipboardRef = useRef<(text?: string) => void>(() => undefined);

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

  useEffect(() => {
    if (!isTauriRuntime()) {
      return;
    }
    void import("@tauri-apps/api/core")
      .then(({ invoke }) => invoke("frontend_ready"))
      .catch(() => {
        // Best effort only; hotkey bridge will still work once the global function is present.
      });
  }, []);

  useEffect(() => {
    configRef.current = config;
  }, [config]);

  useEffect(() => {
    progressRef.current = progress;
  }, [progress]);

  function clearFirstProgressTimeout() {
    if (firstProgressTimeoutRef.current !== null) {
      window.clearTimeout(firstProgressTimeoutRef.current);
      firstProgressTimeoutRef.current = null;
    }
  }

  async function fallbackToBlockingTranslation(reason: string, jobId?: number | null) {
    if (fallbackAttemptedRef.current || !activeRequestTextRef.current) {
      return;
    }

    fallbackAttemptedRef.current = true;
    clearFirstProgressTimeout();
    currentJobIdRef.current = null;
    setProgress(defaultProgressState);
    setStatus(reason);

    if (jobId !== null && jobId !== undefined) {
      try {
        await cancelTranslation(jobId);
      } catch {
        // Best effort only. The blocking fallback should still proceed.
      }
    }

    await runBlockingTranslation(activeRequestTextRef.current);
  }

  function applyTranslationProgress(payload: TranslationProgressEvent) {
    const activeJobId = currentJobIdRef.current;
    if (activeJobId !== null && payload.job_id !== activeJobId) {
      return;
    }
    if (activeJobId === null) {
      currentJobIdRef.current = payload.job_id;
    }

    if (payload.event === "started") {
      clearFirstProgressTimeout();
      setProgress({
        totalSegments: payload.total_segments ?? 0,
        completedSegments: payload.completed_segments ?? 0,
        activeSegmentIndex: null,
        activeSegmentSource: "",
        activeSegmentTarget: "",
        segmentStatus: payload.segment_status ?? "queued",
        partial: false
      });
      setStatus(
        payload.total_segments
          ? `Preparing segment 1/${payload.total_segments} · 0 completed`
          : "Preparing translation..."
      );
      setIsSubmitting(true);
      return;
    }

    if (payload.event === "update") {
      clearFirstProgressTimeout();
      streamProducedOutputRef.current = true;
      if (typeof payload.output_text === "string") {
        setOutput(payload.output_text);
      }
      setProgress({
        totalSegments: payload.total_segments ?? 0,
        completedSegments: payload.completed_segments ?? 0,
        activeSegmentIndex: payload.active_segment_index ?? null,
        activeSegmentSource: payload.active_segment_source ?? "",
        activeSegmentTarget: payload.active_segment_target ?? "",
        segmentStatus: payload.segment_status ?? "queued",
        partial: payload.partial ?? false
      });

      if (payload.detected_source_lang) {
        setLastResponse((current) => ({
          output_text: payload.output_text ?? current?.output_text ?? "",
          segments: current?.segments ?? [],
          detected_source_lang: payload.detected_source_lang ?? null
        }));
      }

      const currentSegment = payload.active_segment_index ?? 0;
      const totalSegments = payload.total_segments ?? 0;
      const completedSegments = payload.completed_segments ?? 0;
      const phase =
        payload.segment_status === "streaming"
          ? "streaming"
          : payload.segment_status === "completed"
            ? "finalized"
            : payload.segment_status === "passthrough"
              ? "passthrough"
              : "queued";
      setStatus(
        totalSegments
          ? `Segment ${currentSegment || "-"} / ${totalSegments} · ${completedSegments} completed · ${phase}`
          : "Translating..."
      );
      return;
    }

    if (payload.event === "completed") {
      clearFirstProgressTimeout();
      streamProducedOutputRef.current = true;
      if (payload.response) {
        setOutput(payload.response.output_text);
        setLastResponse(payload.response);
      } else if (typeof payload.output_text === "string") {
        setOutput(payload.output_text);
      }
      setProgress({
        totalSegments: payload.total_segments ?? progressRef.current.totalSegments,
        completedSegments: payload.total_segments ?? progressRef.current.completedSegments,
        activeSegmentIndex: null,
        activeSegmentSource: "",
        activeSegmentTarget: "",
        segmentStatus: "completed",
        partial: false
      });
      setIsSubmitting(false);
      currentJobIdRef.current = null;
      setStatus(payload.total_segments ? `Done · ${payload.total_segments}/${payload.total_segments} segments` : "Done.");
      return;
    }

    if (payload.event === "canceled") {
      clearFirstProgressTimeout();
      setIsSubmitting(false);
      currentJobIdRef.current = null;
      setStatus(
        progressRef.current.totalSegments
          ? `Canceled · ${progressRef.current.completedSegments}/${progressRef.current.totalSegments} segments finished`
          : "Canceled."
      );
      return;
    }

    if (payload.event === "error") {
      currentJobIdRef.current = null;
      if (!streamProducedOutputRef.current && !fallbackAttemptedRef.current && activeRequestTextRef.current) {
        void fallbackToBlockingTranslation("Desktop streaming failed. Retrying without streaming...");
        return;
      }
      clearFirstProgressTimeout();
      setIsSubmitting(false);
      setStatus(payload.message ?? "Translation failed.");
    }
  }

  async function pollTranslationProgress(jobId: number) {
    while (currentJobIdRef.current === jobId) {
      const events = await takeTranslationEvents<TranslationProgressEvent>(jobId);
      for (const event of events) {
        applyTranslationProgress(event);
      }

      if (currentJobIdRef.current !== jobId) {
        return;
      }

      await new Promise((resolve) => window.setTimeout(resolve, 120));
    }
  }

  useEffect(() => {
    if (!isTauriRuntime()) {
      return;
    }

    translationListenersReadyRef.current = new Promise<void>((resolve) => {
      resolveTranslationListenersReadyRef.current = resolve;
    });

    let unlistenFns: Array<() => void> = [];
    let cancelled = false;

    void import("@tauri-apps/api/event")
      .then(async ({ listen }) => {
        const listeners = await Promise.all([
          listen("translator://tray-opened", () => {
            setStatus("Window restored from tray.");
          }),
          listen("translator://translate-clipboard-requested", () => {
            console.log("frontend: received translate-clipboard-requested");
            setStatus("Hotkey received. Reading clipboard...");
            void handleTranslateClipboard();
          }),
          listen<{ message?: string }>("translator://hotkey-error", (event) => {
            setStatus(event.payload?.message ?? "Global hotkey is unavailable.");
          })
        ]);

        if (cancelled) {
          listeners.forEach((unlisten) => unlisten());
          return;
        }

        unlistenFns = listeners;
        void syncHotkeyListener().catch((error: Error) => {
          setStatus(error.message);
        });
        resolveTranslationListenersReadyRef.current?.();
        resolveTranslationListenersReadyRef.current = null;
      })
      .catch(() => {
        setStatus((current) => current);
        resolveTranslationListenersReadyRef.current?.();
        resolveTranslationListenersReadyRef.current = null;
      });

    return () => {
      cancelled = true;
      clearFirstProgressTimeout();
      unlistenFns.forEach((unlisten) => unlisten());
      resolveTranslationListenersReadyRef.current?.();
      resolveTranslationListenersReadyRef.current = null;
    };
  }, [isBackendReady]);

  function buildRequest(text: string): TranslationRequest {
    const activeConfig = configRef.current;
    return {
      text,
      source_lang: activeConfig.source_lang,
      target_lang: activeConfig.target_lang,
      use_context: activeConfig.use_context,
      collapse_newlines: activeConfig.collapse_newlines,
      output_mode: activeConfig.output_mode,
      mode: activeConfig.mode,
      host: activeConfig.host,
      model: activeConfig.model
    };
  }

  async function runBlockingTranslation(text: string) {
    setIsSubmitting(true);
    try {
      const response = await translate(buildRequest(text));
      setOutput(response.output_text);
      setLastResponse(response);
      setStatus("Done.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Translation failed.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function runTranslation(text: string) {
    if (!text.trim()) {
      setStatus("Nothing to translate.");
      return;
    }

    setInput(text);
    setOutput("");
    setLastResponse(null);
    setProgress(defaultProgressState);
    activeRequestTextRef.current = text;
    streamProducedOutputRef.current = false;
    fallbackAttemptedRef.current = false;

    if (isTauriRuntime() && ENABLE_TAURI_STREAMING) {
      try {
        await translationListenersReadyRef.current;
        setIsSubmitting(true);
        setStatus("Translating...");
        const jobId = await startTranslationStream(buildRequest(text));
        currentJobIdRef.current = jobId;
        void pollTranslationProgress(jobId);
        firstProgressTimeoutRef.current = window.setTimeout(() => {
          void fallbackToBlockingTranslation(
            "Desktop streaming did not produce progress. Retrying without streaming...",
            jobId
          );
        }, 1800);
        return;
      } catch {
        await fallbackToBlockingTranslation("Desktop streaming failed to start. Retrying without streaming...");
        return;
      }
    }

    setStatus("Translating...");
    await runBlockingTranslation(text);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await runTranslation(input);
  }

  async function handleStop() {
    if (!isSubmitting) {
      return;
    }

    if (currentJobIdRef.current === null) {
      setStatus("Current translation is running in fallback mode and cannot be canceled.");
      return;
    }

    try {
      clearFirstProgressTimeout();
      await cancelTranslation(currentJobIdRef.current);
      currentJobIdRef.current = null;
      setIsSubmitting(false);
      setStatus(
        progressRef.current.totalSegments
          ? `Canceled · ${progressRef.current.completedSegments}/${progressRef.current.totalSegments} segments finished`
          : "Canceled."
      );
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Cancel failed.");
    }
  }

  async function handleTranslateClipboard(providedText?: string) {
    if (!isBackendReady) {
      setStatus("Backend is still starting.");
      return;
    }

    try {
      const clipboardText =
        typeof providedText === "string" ? providedText : await readClipboardTextWithRetry();
      console.log("translate-clipboard: length=", clipboardText.length, "preview=", clipboardText.slice(0, 120));
      if (!clipboardText.trim()) {
        setStatus("Clipboard is empty.");
        return;
      }
      await showMainWindow();
      await runTranslation(clipboardText);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Clipboard read failed.");
    }
  }

  async function handleOcrClipboardImage() {
    if (!isBackendReady) {
      setStatus("Backend is still starting.");
      return;
    }

    try {
      setStatus("Running OCR on clipboard image...");
      const text = await runClipboardOcr();
      if (!text.trim()) {
        setStatus("OCR found no text.");
        return;
      }
      setInput(text);
      setStatus("OCR pasted into input.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Clipboard OCR failed.");
    }
  }

  function handleInputPaste(event: ClipboardEvent<HTMLTextAreaElement>) {
    const hasImage = Array.from(event.clipboardData.items).some((item) => item.type.startsWith("image/"));
    if (!hasImage) {
      return;
    }
    event.preventDefault();
    void handleOcrClipboardImage();
  }

  useEffect(() => {
    translateClipboardRef.current = (text?: string) => {
      console.log("frontend: invoked clipboard translation bridge");
      setStatus(typeof text === "string" ? "Hotkey received. Translating clipboard..." : "Hotkey received. Reading clipboard...");
      void handleTranslateClipboard(text);
    };
  });

  useEffect(() => {
    window.__translatorTriggerClipboardTranslation = (text?: string) => {
      translateClipboardRef.current(text);
    };

    return () => {
      // Keep the function stable across re-mounts/HMR whenever possible.
      window.__translatorTriggerClipboardTranslation = undefined;
    };
  }, []);

  async function handleCopyOutput() {
    if (!output.trim()) {
      setStatus("Nothing to copy.");
      return;
    }

    try {
      await writeClipboardText(output);
      setStatus("Output copied to clipboard.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Clipboard write failed.");
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

  const progressRatio =
    progress.totalSegments > 0
      ? Math.min(
          100,
          ((progress.completedSegments + (progress.partial ? 0.45 : 0)) / progress.totalSegments) * 100
        )
      : 0;

  const workPageSettings = (
    <TranslationSettingsForm
      config={config}
      languages={languages}
      onSourceLangChange={(value) => void updateConfig("source_lang", value)}
      onTargetLangChange={(value) => void updateConfig("target_lang", value)}
      onOutputModeChange={(value) => void updateConfig("output_mode", value)}
      onUseContextChange={(checked) => void updateConfig("use_context", checked)}
      onCollapseNewlinesChange={(checked) => void updateConfig("collapse_newlines", checked)}
    />
  );

  const settingsPageContent = (
    <AppSettingsPanel
      config={config}
      onModeChange={(value) => void updateConfig("mode", value)}
      onModelChange={(value) => void updateConfig("model", value)}
      onHostChange={(value) => void updateConfig("host", value)}
      onHotkeyEnabledChange={(checked) => void updateConfig("hotkey_enabled", checked)}
      onMinimizeToTrayChange={(checked) => void updateConfig("minimize_to_tray", checked)}
    />
  );

  const workPageInput = (
    <InputEditor
      value={input}
      onChange={(event) => setInput(event.target.value)}
      onPaste={handleInputPaste}
      rows={12}
    />
  );

  const workPageActions = (
    <div className="actions">
      <div className="action-row">
        <button className="primary" type="submit" disabled={isSubmitting || !isBackendReady}>
          {isSubmitting ? "Translating..." : "Translate"}
        </button>
        <button
          className="ghost action-button"
          type="button"
          disabled={isSubmitting || !isBackendReady}
          onClick={() => void handleTranslateClipboard()}
        >
          Translate clipboard
        </button>
        <button
          className="ghost action-button"
          type="button"
          disabled={isSubmitting || !isBackendReady}
          onClick={() => void handleOcrClipboardImage()}
        >
          OCR clipboard image
        </button>
        <button className="ghost action-button" type="button" disabled={!isSubmitting} onClick={() => void handleStop()}>
          Stop
        </button>
      </div>
      <span className="helper-text">
        Paste text normally. If the clipboard holds an image, paste into Input or use OCR clipboard image to
        extract text first.
      </span>
    </div>
  );

  const workPageControls = (
    <TranslationControls
      onSwapLanguages={swapLanguages}
      swapDisabled={config.source_lang === "auto"}
      settings={workPageSettings}
      input={workPageInput}
      actions={workPageActions}
    />
  );

  const workPageOutput = (
    <OutputPanel
      detectedSourceLanguage={lastResponse?.detected_source_lang}
      output={output}
      onCopy={() => void handleCopyOutput()}
    />
  );

  const workContextPanel = (
    <ContextPanel
      title="Translation progress"
      isOpen={isContextOpen}
      onToggle={() => setIsContextOpen((current) => !current)}
    >
      <TranslationProgressSummary
        progress={progress}
        progressRatio={progressRatio}
        statusLabel={segmentStatusLabel(progress)}
        sourcePreview={compactPreview(progress.activeSegmentSource)}
        targetPreview={compactPreview(progress.activeSegmentTarget, "Target text will stream here.")}
      />
    </ContextPanel>
  );

  function renderActiveView() {
    switch (activeView) {
      case "home":
        return <HomePage />;
      case "history":
        return <HistoryPage />;
      case "resources":
        return <ResourcesPage />;
      case "settings":
        return <SettingsPage>{settingsPageContent}</SettingsPage>;
      case "work":
      default:
        return <WorkPage controls={workPageControls} output={workPageOutput} onSubmit={handleSubmit} />;
    }
  }

  return (
    <AppShell
      topBar={
        <TopBar
          eyebrow="Local Desktop Translator"
          title="Single UI, Python brain, Tauri shell"
          actions={
            activeView === "work" ? (
              <button className="ghost" type="button" onClick={() => setIsContextOpen((current) => !current)}>
                {isContextOpen ? "Hide context" : "Show context"}
              </button>
            ) : null
          }
        />
      }
      sidebar={<Sidebar activeView={activeView} onSelect={setActiveView} />}
      statusBar={<StatusBar status={status} isReady={isBackendReady} />}
      contextPanel={activeView === "work" ? workContextPanel : undefined}
    >
      {renderActiveView()}
    </AppShell>
  );
}
