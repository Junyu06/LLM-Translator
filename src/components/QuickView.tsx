import { useEffect, useRef, useState } from "react";

import { languageName, translator } from "../i18n";
import { IconCopy, IconExpand, IconX } from "../icons";
import {
  cancelTranslation,
  getConfig,
  hideQuickWindow,
  isTauriRuntime,
  passQuickResult,
  quickFrontendReady,
  readClipboard,
  startTranslationStream,
  takeTranslationEvents,
  translate,
  writeClipboardText
} from "../lib/api";
import { defaultConfig, requestFor } from "../lib/defaults";
import type { AppConfig, QuickResult, TranslationEvent } from "../types";
import TranslationView from "./TranslationView";
import "../styles.css";

type Phase = "idle" | "reading" | "translating" | "done" | "error";

const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));
const errorText = (error: unknown) => (error instanceof Error ? error.message : String(error));

// The small window that copying twice opens next to the pointer: the
// translation only, with copy, Return to open it in the main window, and Esc
// to go back.
export default function QuickView() {
  const [config, setConfig] = useState<AppConfig>(defaultConfig);
  const [phase, setPhase] = useState<Phase>("idle");
  const [message, setMessage] = useState("");
  const [result, setResult] = useState<QuickResult | null>(null);
  const [copied, setCopied] = useState(false);
  const runRef = useRef(0);
  const jobRef = useRef<number | null>(null);
  const shownAtRef = useRef(0);
  const t = translator(config.ui_lang);

  const run = async () => {
    const id = runRef.current + 1;
    runRef.current = id;
    // A new double copy replaces the translation still running here.
    if (jobRef.current !== null) void cancelTranslation(jobRef.current);
    jobRef.current = null;
    shownAtRef.current = Date.now();
    setPhase("reading");
    setResult(null);
    setMessage("");
    setCopied(false);

    let current = defaultConfig;
    try {
      current = { ...defaultConfig, ...(await getConfig()) };
    } catch (error) {
      console.error(error);
    }
    if (runRef.current !== id) return;
    setConfig(current);
    document.body.setAttribute("data-theme", current.theme || "system");
    const tr = translator(current.ui_lang);

    // Right after a double copy the source app may still be writing the clipboard.
    let text = "";
    let source: "text" | "image" | "empty" = "empty";
    for (let attempt = 0; attempt < 3 && source === "empty"; attempt += 1) {
      if (attempt > 0) await sleep(80);
      try {
        const capture = await readClipboard();
        source = capture.source;
        text = capture.text;
      } catch (error) {
        if (runRef.current !== id) return;
        setPhase("error");
        setMessage(`${tr("clipboard_error")}: ${errorText(error)}`);
        return;
      }
    }
    if (runRef.current !== id) return;
    if (!text.trim()) {
      setPhase("error");
      setMessage(source === "image" ? tr("ocr_no_text") : tr("clipboard_empty"));
      return;
    }

    setPhase("translating");
    setResult({ source: text, output: "", segments: [], detected_source_lang: null });
    const finish = (finished: QuickResult) => {
      setResult(finished);
      setPhase("done");
      void passQuickResult(finished, false).catch((error) => console.error(error));
    };
    const fail = (error: string) => {
      setPhase("error");
      setMessage(error);
    };

    if (!isTauriRuntime()) {
      try {
        const response = await translate(requestFor(text, current));
        if (runRef.current !== id) return;
        finish({
          source: text,
          output: response.output_text,
          segments: response.segments.map((segment) => ({ ...segment, done: true })),
          detected_source_lang: response.detected_source_lang
        });
      } catch (error) {
        if (runRef.current === id) fail(errorText(error));
      }
      return;
    }

    // Streamed, so paragraphs appear as they are translated.
    let jobId: number;
    try {
      jobId = await startTranslationStream(requestFor(text, current));
    } catch (error) {
      if (runRef.current === id) fail(errorText(error));
      return;
    }
    if (runRef.current !== id) {
      void cancelTranslation(jobId);
      return;
    }
    jobRef.current = jobId;
    let latest: QuickResult = { source: text, output: "", segments: [], detected_source_lang: null };
    while (runRef.current === id) {
      let events: TranslationEvent[];
      try {
        events = await takeTranslationEvents<TranslationEvent>(jobId);
      } catch (error) {
        if (runRef.current === id) fail(errorText(error));
        return;
      }
      if (runRef.current !== id) return;
      for (const event of events) {
        latest = {
          source: text,
          output: event.output_text ?? latest.output,
          segments: event.segments ?? latest.segments,
          detected_source_lang: event.detected_source_lang ?? latest.detected_source_lang
        };
        if (event.event === "completed") {
          jobRef.current = null;
          finish(latest);
          return;
        }
        if (event.event === "error") {
          jobRef.current = null;
          fail(event.message ?? "Translation failed");
          return;
        }
        if (event.event === "canceled") return;
      }
      setResult(latest);
      await sleep(120);
    }
  };

  const close = () => void hideQuickWindow(true);

  const copy = async () => {
    if (!result?.output) return;
    try {
      await writeClipboardText(result.output);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch (error) {
      setMessage(errorText(error));
    }
  };

  // Return: a finished translation moves to the main window as it is; one
  // still running (or failed) is translated again there.
  const openInMain = () => {
    const finished = phase === "done" && result !== null;
    if (!finished) {
      runRef.current += 1;
      if (jobRef.current !== null) void cancelTranslation(jobRef.current);
      jobRef.current = null;
    }
    const handoff: QuickResult = finished
      ? result
      : { source: result?.source ?? "", output: "", segments: [], detected_source_lang: null, unfinished: true };
    void passQuickResult(handoff, true).catch((error) => setMessage(errorText(error)));
  };

  // Handlers change every render; the window-level listeners below read the latest ones.
  const handlersRef = useRef({ run, close, openInMain });
  handlersRef.current = { run, close, openInMain };

  useEffect(() => {
    (globalThis as any).__translatorQuickTranslate = () => void handlersRef.current.run();
    void quickFrontendReady().catch((error) => console.error(error));
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") handlersRef.current.close();
      if (event.key === "Enter" && !event.isComposing) {
        // Not also a click on whichever button has focus.
        event.preventDefault();
        handlersRef.current.openInMain();
      }
    };
    // Clicking another app dismisses the window. A blur in the moment the
    // window is being shown is checked again once it has settled.
    let recheck: number | undefined;
    const onBlur = () => {
      const settling = 600 - (Date.now() - shownAtRef.current);
      if (settling <= 0) {
        void hideQuickWindow(false);
        return;
      }
      window.clearTimeout(recheck);
      recheck = window.setTimeout(() => {
        if (!document.hasFocus()) void hideQuickWindow(false);
      }, settling);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("blur", onBlur);
    return () => {
      delete (globalThis as any).__translatorQuickTranslate;
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("blur", onBlur);
      window.clearTimeout(recheck);
    };
  }, []);

  const lang = (code: string) => languageName(config.ui_lang, code);
  const from = result?.detected_source_lang ?? (config.source_lang === "auto" ? null : config.source_lang);
  const route = `${from ? lang(from) : lang("auto")} → ${lang(config.target_lang)}`;
  const busy = phase === "reading" || phase === "translating";

  return (
    <div className="quick" style={{ fontSize: `${config.font_size}px` }}>
      <header className="quick-bar">
        <span className="panel-label">{route}</span>
        <div className="row-actions">
          <button className="icon-btn" onClick={() => void copy()} disabled={phase !== "done"} title={t(copied ? "copied" : "copy")}><IconCopy /></button>
          <button className="icon-btn" onClick={openInMain} title={t("open_in_main")}><IconExpand /></button>
          <button className="icon-btn" onClick={close} title={t("close_quick")}><IconX /></button>
        </div>
      </header>
      <div className="quick-body">
        {phase === "error" ? (
          <p className="quick-message status-error">{message}</p>
        ) : phase === "reading" ? (
          <p className="quick-message">{t("reading_clipboard")}</p>
        ) : (
          <TranslationView
            t={t}
            segments={result?.segments ?? []}
            outputText={result?.output ?? ""}
            bilingual={false}
            markdown={config.translation_mode === "markdown"}
            running={busy}
            retranslating={new Set()}
            actions={false}
            onCopy={() => {}}
            onRetranslate={() => {}}
            emptyHint=""
          />
        )}
      </div>
      {copied && <div className="quick-toast">{t("copied")}</div>}
      {phase !== "error" && message && <div className="quick-toast error">{message}</div>}
    </div>
  );
}
