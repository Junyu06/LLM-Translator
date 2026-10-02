import type { AppConfig, QuickResult, TranslationRequest, TranslationResponse } from "../types";

const API_BASE = "http://127.0.0.1:8765";

export type DesktopBackendStatus = {
  state: "running" | "stopped";
  python: string | null;
  error: string | null;
};

export type HotkeyStatus = {
  state: string;
  error: string | null;
};

export type ClipboardCapture = {
  source: "text" | "image" | "empty";
  text: string;
};

type BridgeError = {
  error?: string;
  command?: string;
  python?: string;
  python3_in_path?: string | null;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json"
    },
    ...init
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed: ${response.status}`);
  }

  return (await response.json()) as T;
}

async function invokeJson<T>(command: string, payload?: unknown): Promise<T> {
  const { invoke } = await import("@tauri-apps/api/core");
  try {
    const raw = await invoke<string>(command, payload ? { payload: JSON.stringify(payload) } : {});
    return JSON.parse(raw) as T;
  } catch (error) {
    if (typeof error === "string") {
      let parsed: BridgeError | undefined;
      try {
        parsed = JSON.parse(error) as BridgeError;
      } catch {
        throw new Error(error);
      }
      if (parsed?.error) {
        throw new Error(parsed.python ? `${parsed.error} (${parsed.python})` : parsed.error);
      }
    }
    throw error;
  }
}

async function invokeRaw<T>(command: string, payload?: unknown): Promise<T> {
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<T>(command, payload ? { payload: JSON.stringify(payload) } : {});
}

async function invokeVoid(command: string, payload?: unknown): Promise<void> {
  const { invoke } = await import("@tauri-apps/api/core");
  if (payload === undefined) {
    await invoke(command);
    return;
  }
  await invoke(command, { payload });
}

export async function getHealth(): Promise<{ status: string }> {
  if (isTauriRuntime()) {
    const desktopStatus = await getDesktopBackendStatus();
    if (desktopStatus?.state === "running") {
      return { status: "ok" };
    }
    throw new Error(desktopStatus?.error ?? "Python bridge is not ready.");
  }
  return request("/health");
}

export async function getConfig(): Promise<AppConfig> {
  if (isTauriRuntime()) {
    return invokeJson<AppConfig>("get_config");
  }
  return request("/config");
}

export async function saveConfig(config: Partial<AppConfig>): Promise<AppConfig> {
  if (isTauriRuntime()) {
    return invokeJson<AppConfig>("save_config", config);
  }
  return request("/config", {
    method: "PUT",
    body: JSON.stringify(config)
  });
}

export async function translate(payload: TranslationRequest): Promise<TranslationResponse> {
  if (isTauriRuntime()) {
    return invokeJson<TranslationResponse>("translate", payload);
  }
  return request("/translate", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export async function listModels(config: Pick<AppConfig, "mode" | "host">): Promise<string[]> {
  if (isTauriRuntime()) {
    const result = await invokeJson<{ models: string[] }>("list_models", { mode: config.mode, host: config.host });
    return result.models;
  }
  const host = config.mode === "http" && config.host.trim() ? config.host.trim().replace(/\/+$/, "") : "http://127.0.0.1:11434";
  const response = await fetch(`${host}/api/tags`);
  const body = (await response.json()) as { models?: Array<{ name: string }> };
  return (body.models ?? []).map((model) => model.name).sort();
}

export async function startTranslationStream(payload: TranslationRequest): Promise<number> {
  if (!isTauriRuntime()) {
    throw new Error("Streaming translation is only available in the Tauri runtime.");
  }
  return invokeRaw<number>("start_translation_stream", payload);
}

export async function takeTranslationEvents<T>(jobId: number): Promise<T[]> {
  if (!isTauriRuntime()) {
    return [];
  }
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<T[]>("take_translation_events", {
    jobId
  });
}

export async function cancelTranslation(jobId?: number | null): Promise<boolean> {
  if (!isTauriRuntime()) {
    return false;
  }
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<boolean>("cancel_translation", {
    jobId: jobId ?? null
  });
}

export function isTauriRuntime() {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export async function getDesktopBackendStatus(): Promise<DesktopBackendStatus | null> {
  if (!isTauriRuntime()) {
    return null;
  }
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<DesktopBackendStatus>("backend_status");
}

export async function refreshBackendStatus(): Promise<DesktopBackendStatus | null> {
  if (isTauriRuntime()) {
    return getDesktopBackendStatus();
  }

  try {
    await getHealth();
    return {
      state: "running",
      python: null,
      error: null
    };
  } catch (error) {
    return {
      state: "stopped",
      python: null,
      error: error instanceof Error ? error.message : "Backend health check failed."
    };
  }
}

export async function getHotkeyStatus(): Promise<HotkeyStatus | null> {
  if (!isTauriRuntime()) {
    return null;
  }

  const { invoke } = await import("@tauri-apps/api/core");
  try {
    return await invoke<HotkeyStatus>("hotkey_status");
  } catch (error) {
    return {
      state: "unknown",
      error: error instanceof Error ? error.message : String(error)
    };
  }
}

export async function onHotkeyError(callback: (message: string) => void): Promise<() => void> {
  if (!isTauriRuntime()) {
    return () => {};
  }

  const { listen } = await import("@tauri-apps/api/event");
  return listen<{ message?: string }>("translator://hotkey-error", (event) => {
    callback(event.payload?.message || "Windows hotkey listener failed.");
  });
}

export async function syncHotkeyListener(): Promise<void> {
  if (!isTauriRuntime()) {
    return;
  }
  await invokeVoid("sync_hotkey_listener");
}

// Text comes back as-is; an image comes back as OCR text with source "image".
export async function readClipboard(): Promise<ClipboardCapture> {
  if (isTauriRuntime()) {
    return invokeJson<ClipboardCapture>("read_clipboard");
  }

  if (typeof navigator !== "undefined" && navigator.clipboard?.readText) {
    const text = await navigator.clipboard.readText();
    return { source: text.trim() ? "text" : "empty", text };
  }

  throw new Error("Clipboard read is not available in this runtime.");
}

export async function writeClipboardText(text: string): Promise<void> {
  // Web Clipboard API works in Tauri webview (with user gesture) and browser
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  // Fallback: Tauri native bridge
  if (isTauriRuntime()) {
    await invokeVoid("write_clipboard_text", text);
    return;
  }

  throw new Error("Clipboard write is not available in this runtime.");
}

export async function checkAccessibility(): Promise<boolean> {
  if (!isTauriRuntime()) return true;
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<boolean>("check_accessibility");
}

export async function requestAccessibility(): Promise<boolean> {
  if (!isTauriRuntime()) return true;
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<boolean>("request_accessibility");
}

export async function openPrivacySettings(page: "input_monitoring" | "accessibility"): Promise<void> {
  if (!isTauriRuntime()) return;
  const { invoke } = await import("@tauri-apps/api/core");
  await invoke("open_privacy_settings", { page });
}

export async function checkInputMonitoring(): Promise<boolean> {
  if (!isTauriRuntime()) return true;
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<boolean>("check_input_monitoring");
}

export async function requestInputMonitoring(): Promise<boolean> {
  if (!isTauriRuntime()) return true;
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<boolean>("request_input_monitoring");
}

export async function notifyFrontendReady(): Promise<void> {
  if (!isTauriRuntime()) return;
  await invokeVoid("frontend_ready");
}

export async function loadInitialConfig(): Promise<{
  config: AppConfig;
  desktopStatus: DesktopBackendStatus | null;
}> {
  const config = await getConfig();
  return {
    config,
    desktopStatus: null
  };
}

// ---------- quick window ----------

export async function quickFrontendReady(): Promise<void> {
  if (!isTauriRuntime()) return;
  const { invoke } = await import("@tauri-apps/api/core");
  await invoke("quick_frontend_ready");
}

// `returnFocus`: hand focus back to the app the text came from (Esc, close).
export async function hideQuickWindow(returnFocus: boolean): Promise<void> {
  if (!isTauriRuntime()) return;
  const { invoke } = await import("@tauri-apps/api/core");
  await invoke("hide_quick_window", { returnFocus });
}

// Every finished quick translation goes to the main window's history; `show` also opens it there.
export async function passQuickResult(result: QuickResult, show: boolean): Promise<void> {
  if (!isTauriRuntime()) return;
  const { invoke } = await import("@tauri-apps/api/core");
  await invoke("quick_result", { payload: JSON.stringify(result), show });
}

export function isQuickWindow(): boolean {
  if (typeof window === "undefined") return false;
  const label = (window as any).__TAURI_INTERNALS__?.metadata?.currentWindow?.label;
  return label === "quick" || new URLSearchParams(window.location.search).get("view") === "quick";
}
