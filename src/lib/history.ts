import type { HistoryItem, TranslationSegment } from "../types";

const HISTORY_KEY = "translator_history_v2";
const HISTORY_LIMIT = 100;

// localStorage can throw (private mode, quota), so every access is guarded.
export function readStorage(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch (error) {
    console.error(error);
    return null;
  }
}

export function writeStorage(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch (error) {
    console.error(error);
  }
}

const isSegment = (value: unknown): value is TranslationSegment => {
  const segment = value as Partial<TranslationSegment>;
  return !!segment && typeof segment.source === "string" && typeof segment.target === "string";
};

const isHistoryItem = (value: unknown): value is HistoryItem => {
  const item = value as Partial<HistoryItem>;
  return (
    !!item &&
    typeof item.id === "string" &&
    typeof item.source === "string" &&
    typeof item.target === "string" &&
    typeof item.timestamp === "number" &&
    (item.segments === undefined || (Array.isArray(item.segments) && item.segments.every(isSegment)))
  );
};

export function loadHistory(): HistoryItem[] {
  const saved = readStorage(HISTORY_KEY);
  if (!saved) return [];
  try {
    const parsed = JSON.parse(saved);
    if (Array.isArray(parsed)) return parsed.filter(isHistoryItem);
  } catch (error) {
    console.error(error);
  }
  // Keep the unreadable value instead of overwriting it on the next save.
  writeStorage(`${HISTORY_KEY}_corrupt_${Date.now()}`, saved);
  return [];
}

export function saveHistory(history: HistoryItem[]) {
  writeStorage(HISTORY_KEY, JSON.stringify(history));
}

export function addHistoryItem(
  history: HistoryItem[],
  source: string,
  target: string,
  segments: TranslationSegment[]
): HistoryItem[] {
  const trimmed = source.trim();
  if (!trimmed || !target.trim()) return history;
  const item: HistoryItem = {
    id: Math.random().toString(36).slice(2, 9),
    source: trimmed,
    target: target.trim(),
    timestamp: Date.now(),
    segments
  };
  return [item, ...history.filter((existing) => existing.source !== trimmed)].slice(0, HISTORY_LIMIT);
}
