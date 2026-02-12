// Shared helpers for frontend chat pages.
// Motivation: reduce duplicated page glue code across rag.ts and agentic.ts.

export function bindClampedNumberInput(input: HTMLInputElement, min: number, max: number): void {
  const clamp = (): void => {
    const value = Number(input.value);
    if (value < min) input.value = String(min);
    if (value > max) input.value = String(max);
  };
  input.addEventListener("input", clamp);
  input.addEventListener("change", clamp);
}

export function loadSettingsFromStorage<T extends { chunkIndex?: string | null }>(
  storageKey: string,
  defaults: T
): T {
  let settings: T = defaults;
  try {
    const raw = localStorage.getItem(storageKey);
    if (raw) {
      settings = { ...defaults, ...JSON.parse(raw) };
    }
  } catch {
    // Keep defaults on parse/storage errors.
  }

  const params = new URLSearchParams(window.location.search);
  const urlChunkIndex = params.get("chunk_index");
  if (urlChunkIndex !== null && Object.prototype.hasOwnProperty.call(settings, "chunkIndex")) {
    (settings as { chunkIndex?: string | null }).chunkIndex = urlChunkIndex.trim();
  }
  return settings;
}

export function saveSettingsToStorage<T>(storageKey: string, settings: T): void {
  localStorage.setItem(storageKey, JSON.stringify(settings));
}

export interface RateLimitController {
  clear: () => void;
  start: (seconds: number) => void;
  isActive: () => boolean;
}

export function createRateLimitController(
  sendBtn: HTMLButtonElement,
  setStatusText: (text: string, isError?: boolean) => void
): RateLimitController {
  let timer: ReturnType<typeof setInterval> | null = null;

  const clear = (): void => {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
  };

  const start = (seconds: number): void => {
    // Always reset prior countdown so repeated 429 responses extend from latest server directive.
    clear();
    let remaining = Math.max(1, Math.floor(seconds || 1));
    sendBtn.disabled = true;
    setStatusText(`Rate limited (${remaining}s)`, true);
    timer = setInterval(() => {
      remaining -= 1;
      if (remaining <= 0) {
        clear();
        setStatusText("Idle");
        sendBtn.disabled = false;
        return;
      }
      setStatusText(`Rate limited (${remaining}s)`, true);
    }, 1000);
  };

  const isActive = (): boolean => timer !== null;

  return { clear, start, isActive };
}

