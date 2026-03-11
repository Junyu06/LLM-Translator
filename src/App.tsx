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

  return (
    <main className="shell">
      <header className="masthead">
        <div className="title-block">
          <div>
            <p className="eyebrow">Local Desktop Translator</p>
            <h1>Single UI, Python brain, Tauri shell</h1>
          </div>
          <div className="progress-board">
            <div className="progress-stats">
              <span>{progress.activeSegmentIndex ? `Segment ${progress.activeSegmentIndex}` : "Waiting"}</span>
              <span>{progress.totalSegments ? `${progress.completedSegments}/${progress.totalSegments} done` : "0/0 done"}</span>
              <span>{segmentStatusLabel(progress)}</span>
            </div>
            <div className="progress-rail">
              <div className="progress-fill" style={{ width: `${progressRatio}%` }} />
            </div>
            <div className="segment-card">
              <p className="segment-label">Current Source</p>
              <p>{compactPreview(progress.activeSegmentSource)}</p>
              <p className="segment-label">Current Target</p>
              <p>{compactPreview(progress.activeSegmentTarget, "Target text will stream here.")}</p>
            </div>
          </div>
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

            <label className="toggle-card">
              <input
                type="checkbox"
                checked={config.hotkey_enabled}
                onChange={(event) => void updateConfig("hotkey_enabled", event.target.checked)}
              />
              <span>
                <strong>Double-Copy Hotkey</strong>
                <em>Use Cmd+C Cmd+C on macOS or Ctrl+C Ctrl+C on Windows.</em>
              </span>
            </label>

            <label className="toggle-card">
              <input
                type="checkbox"
                checked={config.minimize_to_tray}
                onChange={(event) => void updateConfig("minimize_to_tray", event.target.checked)}
              />
              <span>
                <strong>Minimize To Tray</strong>
                <em>Closing the desktop window hides it instead of quitting the app.</em>
              </span>
            </label>
          </div>

          <label className="field">
            <span className="field-label">Input</span>
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onPaste={handleInputPaste}
              rows={12}
            />
          </label>

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
              <button
                className="ghost action-button"
                type="button"
                disabled={!isSubmitting}
                onClick={() => void handleStop()}
              >
                Stop
              </button>
            </div>
            <span className="helper-text">Paste text normally. If the clipboard holds an image, paste into Input or use OCR clipboard image to extract text first.</span>
          </div>
        </form>

        <section className="panel output">
          <div className="output-header">
            <div>
              <p className="section-kicker">Output</p>
              <h2>Rendered translation</h2>
            </div>
            <div className="output-tools">
              <span className="output-meta">
                {lastResponse?.detected_source_lang
                  ? `Detected: ${lastResponse.detected_source_lang}`
                  : "Awaiting input"}
              </span>
              <button className="ghost action-button" type="button" onClick={() => void handleCopyOutput()}>
                Copy output
              </button>
            </div>
          </div>
          <pre>{output || "Translation result will appear here, segment by segment."}</pre>
        </section>
      </section>
    </main>
  );
}
