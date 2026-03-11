import type { AppConfig, TranslationRequest, TranslationResponse } from "../types";

const API_BASE = "http://127.0.0.1:8765";

export type DesktopBackendStatus = {
  state: "running" | "stopped";
  python: string | null;
  error: string | null;
};

type OcrResponse = {
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
      try {
        const parsed = JSON.parse(error) as BridgeError;
        if (parsed.error) {
          throw new Error(parsed.python ? `${parsed.error} (${parsed.python})` : parsed.error);
        }
      } catch {
        throw new Error(error);
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

export async function showMainWindow(): Promise<void> {
  if (!isTauriRuntime()) {
    return;
  }
  await invokeVoid("show_main_window_command");
}

export async function syncHotkeyListener(): Promise<void> {
  if (!isTauriRuntime()) {
    return;
  }
  await invokeVoid("sync_hotkey_listener");
}

export async function readClipboardText(): Promise<string> {
  if (isTauriRuntime()) {
    return invokeRaw<string>("read_clipboard_text");
  }

  if (typeof navigator !== "undefined" && navigator.clipboard?.readText) {
    return navigator.clipboard.readText();
  }

  throw new Error("Clipboard read is not available in this runtime.");
}

export async function writeClipboardText(text: string): Promise<void> {
  if (isTauriRuntime()) {
    await invokeVoid("write_clipboard_text", text);
    return;
  }

  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  throw new Error("Clipboard write is not available in this runtime.");
}

export async function runClipboardOcr(): Promise<string> {
  if (!isTauriRuntime()) {
    throw new Error("Clipboard OCR is only available in the Tauri runtime.");
  }
  const result = await invokeJson<OcrResponse>("run_clipboard_ocr");
  return result.text;
}

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export async function waitForBackend(timeoutMs = 12000) {
  const deadline = Date.now() + timeoutMs;
  let lastError = "Backend did not become ready in time.";

  while (Date.now() < deadline) {
    try {
      const [health, config] = await Promise.all([getHealth(), getConfig()]);
      if (health.status === "ok") {
        return {
          config,
          desktopStatus: await getDesktopBackendStatus()
        };
      }
    } catch (error) {
      lastError = error instanceof Error ? error.message : "Load failed";
    }
    await sleep(350);
  }

  const desktopStatus = await getDesktopBackendStatus();
  if (desktopStatus?.error) {
    throw new Error(desktopStatus.error);
  }
  throw new Error(lastError);
}
