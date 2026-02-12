// Shared helpers for frontend chat pages.
// Motivation: reduce duplicated page glue code across rag.ts and agentic.ts.
export function bindClampedNumberInput(input, min, max) {
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
export function saveSettingsToStorage(storageKey, settings) {
    localStorage.setItem(storageKey, JSON.stringify(settings));
}
export function createRateLimitController(sendBtn, setStatusText) {
    let timer = null;
    const clear = () => {
        if (timer) {
            clearInterval(timer);
            timer = null;
        }
    };
    const start = (seconds) => {
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
    const isActive = () => timer !== null;
    return { clear, start, isActive };
}
