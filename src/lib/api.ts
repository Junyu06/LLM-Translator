import type { AppConfig, TranslationRequest, TranslationResponse } from "../types";

const API_BASE = "http://127.0.0.1:8765";

export type DesktopBackendStatus = {
  state: "running" | "stopped";
  python: string | null;
  error: string | null;
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

function isTauriRuntime() {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export async function getDesktopBackendStatus(): Promise<DesktopBackendStatus | null> {
  if (!isTauriRuntime()) {
    return null;
  }
  const { invoke } = await import("@tauri-apps/api/core");
  return invoke<DesktopBackendStatus>("backend_status");
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
