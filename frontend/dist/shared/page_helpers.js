// Shared helpers for frontend chat pages.
// Motivation: reduce duplicated page glue code across rag.ts and agentic.ts.
// Keep numeric inputs within backend-accepted bounds at entry time to prevent invalid requests.
export function bindClampedNumberInput(input, min, max) {
    // Normalize values on both typing and blur so UI state always stays valid before submit.
    const clamp = () => {
        const value = Number(input.value);
        if (value < min)
            input.value = String(min);
        if (value > max)
            input.value = String(max);
    };
    input.addEventListener("input", clamp);
    input.addEventListener("change", clamp);
}
// Restore persisted settings with safe defaults and allow URL params to override for shareable links.
export function loadSettingsFromStorage(storageKey, defaults) {
    let settings = defaults;
    try {
        const raw = localStorage.getItem(storageKey);
        if (raw) {
            settings = { ...defaults, ...JSON.parse(raw) };
        }
    }
    catch {
        // Keep defaults on parse/storage errors.
    }
    const params = new URLSearchParams(window.location.search);
    const urlChunkIndex = params.get("chunk_index");
    if (urlChunkIndex !== null && Object.prototype.hasOwnProperty.call(settings, "chunkIndex")) {
        settings.chunkIndex = urlChunkIndex.trim();
    }
    return settings;
}
// Persist page settings as JSON so users keep their preferred retrieval parameters across sessions.
export function saveSettingsToStorage(storageKey, settings) {
    localStorage.setItem(storageKey, JSON.stringify(settings));
}
// Centralize 429 cooldown behavior so all chat pages show a consistent countdown and button state.
export function createRateLimitController(sendBtn, setStatusText) {
    let timer = null;
    // Stop any active countdown before starting a new one or when requests become available again.
    const clear = () => {
        if (timer) {
            clearInterval(timer);
            timer = null;
        }
    };
    // Disable send and display server-provided retry window to prevent pointless repeated requests.
    const start = (seconds) => {
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
    // Let callers preserve disabled state while a cooldown timer is still running.
    const isActive = () => timer !== null;
    return { clear, start, isActive };
}
