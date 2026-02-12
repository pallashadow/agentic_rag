import type { Source, RAGSettings, MessageOptions, RAGResponse, SSEChunk } from "./types.js";
import {
  buildEndpointUrl,
  setStatus,
  nowTime,
  typewriterEffect,
  copyToClipboard,
  fetchAuthTokenFromBackend,
  getAuthToken,
  clearTokenCache,
} from "./common.js";
import {
  bindClampedNumberInput,
  createRateLimitController,
  loadSettingsFromStorage,
  saveSettingsToStorage,
} from "./shared/page_helpers.js";

const STORAGE_KEY = "chatbot-milesguo:settings:v1";

// Global DOM element references
let cloudBase: HTMLInputElement;
let titleK: HTMLInputElement;
let chunkK: HTMLInputElement;
let queryExpandK: HTMLInputElement;
let chunkIndex: HTMLInputElement;
let statusPill: HTMLElement;
let saveBtn: HTMLButtonElement;
let resetBtn: HTMLButtonElement;
let clearBtn: HTMLButtonElement;
let showSources: HTMLInputElement;
let messages: HTMLElement;
let userInput: HTMLTextAreaElement;
let sendBtn: HTMLButtonElement;
let cancelBtn: HTMLButtonElement;
let errorLine: HTMLElement;

// Render expandable source diagnostics so users can verify where each answer fragment came from.
function renderSourcesDetails(
  container: HTMLElement,
  sources: Source[],
  { includeIndex = true }: { includeIndex?: boolean } = {}
): void {
  // Accept backend payloads directly and no-op on empty results to keep callers simple.
  if (!sources || !Array.isArray(sources) || sources.length === 0) return;

  const details = document.createElement("details");
  details.open = !!showSources.checked;

  const summary = document.createElement("summary");
  summary.textContent = `Sources (${sources.length})`;
  details.appendChild(summary);

  const list = document.createElement("div");
  list.className = "sources";

  for (const s of sources) {
    const item = document.createElement("div");
    item.className = "sourceItem";

    const title = document.createElement("p");
    title.className = "sourceTitle";
    title.textContent = s.doc_title || "(untitled)";

    const metaP = document.createElement("p");
    metaP.className = "sourceMeta";
    const index = s.index ?? "";
    const chunkId = s.chunk_id ?? "";
    const docId = s.doc_id ?? "";
    const score =
      s.score != null ? Number(s.score).toFixed(4) : "";
    const indexPrefix = includeIndex && index !== "" ? `#${index}   ` : "";
    metaP.textContent = `${indexPrefix}doc_id: ${docId}   chunk_id: ${chunkId}   score: ${score}`;

    const textP = document.createElement("p");
    textP.className = "sourceText";
    textP.textContent = s.text ? `Chunk: ${s.text}` : "";

    const summaryText = s.doc_summary || s.summary || "";
    if (summaryText) {
      const summaryP = document.createElement("p");
      summaryP.className = "sourceText";
      summaryP.textContent = `Summary: ${summaryText}`;
      item.appendChild(summaryP);
    }

    const context = s.context || "";
    if (context) {
      const contextP = document.createElement("p");
      contextP.className = "sourceText";
      contextP.textContent = `Context: ${context}`;
      item.appendChild(contextP);
    }

    item.appendChild(title);
    item.appendChild(metaP);
    item.appendChild(textP);
    list.appendChild(item);
  }

  details.appendChild(list);
  container.appendChild(details);
}

// Show a compact progress badge that confirms retrieval produced source candidates.
function renderSourcesProgress(container: HTMLElement, sources: Source[]): void {
  if (!sources || !Array.isArray(sources) || sources.length === 0) return;
  const progressDiv = document.createElement("div");
  progressDiv.className = "progressIndicator fadeIn";
  progressDiv.innerHTML = `
          <div class="progressDot"></div>
          <span class="progressText">Found ${sources.length} source${sources.length !== 1 ? "s" : ""}</span>
        `;
  container.appendChild(progressDiv);
}

// Create or refresh a chat bubble while keeping message actions and debug sections in sync.
function addMessage(options: MessageOptions): HTMLElement {
  const {
    role,
    text = null,
    sources = null,
    prompt = null,
    querys = null,
    thinking = false,
    updateBubble = null,
    useTypewriter = true,
  } = options;

  // If updateBubble is provided, update existing message instead of creating new one
  if (updateBubble) {
    const pre = updateBubble.querySelector(".msg");
    if (pre) {
      if (thinking) {
        pre.innerHTML = '<span class="thinking">Thinking</span>';
      } else {
        // Remove typing class if present
        pre.classList.remove("typing");
        if (useTypewriter && text) {
          typewriterEffect(messages, pre as HTMLElement, text);
        } else {
          pre.textContent = text || "";
        }
      }
    }

    // Recreate dynamic sections each update so streaming refreshes do not stack duplicated UI.
    // Remove existing progress indicator if any
    const existingProgress = updateBubble.querySelectorAll(".progressIndicator");
    existingProgress.forEach((p) => p.remove());

    // Remove existing sources/details if any
    const existingDetails = updateBubble.querySelectorAll("details");
    existingDetails.forEach((d) => d.remove());

    // Add new sources if provided
    if (role === "assistant") {
      renderSourcesProgress(updateBubble, sources || []);
      renderSourcesDetails(updateBubble, sources || [], { includeIndex: false });
    }

    messages.scrollTop = messages.scrollHeight;
    return updateBubble;
  }

  const bubble = document.createElement("div");
  bubble.className = `bubble ${role}`;

  const meta = document.createElement("div");
  meta.className = "meta";

  const metaLeft = document.createElement("span");
  metaLeft.textContent = role === "user" ? "You" : "Assistant";

  const metaRight = document.createElement("span");
  metaRight.textContent = nowTime();

  // Add message action buttons
  const messageActions = document.createElement("div");
  messageActions.className = "messageActions";

  if (role === "user" && !thinking) {
    const editBtn = document.createElement("button");
    editBtn.className = "messageActionBtn";
    editBtn.innerHTML = "✏️ Edit";
    editBtn.title = "Edit message";
    editBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      // Put text back into input
      userInput.value = text || "";
      userInput.focus();
      // Remove this message and all following messages
      const allBubbles = Array.from(messages.children);
      const currentIndex = allBubbles.indexOf(bubble);
      for (let i = currentIndex + 1; i < allBubbles.length; i++) {
        allBubbles[i].remove();
      }
      // Update query context
      const removedCount = allBubbles.length - currentIndex - 1;
      queryContext = queryContext.slice(0, -removedCount * 2);
    });
    messageActions.appendChild(editBtn);
  }

  if (role === "assistant" && !thinking) {
    const copyBtn = document.createElement("button");
    copyBtn.className = "messageActionBtn";
    copyBtn.innerHTML = "📋 Copy";
    copyBtn.title = "Copy message";
    copyBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const success = await copyToClipboard(text || "");
      if (success) {
        copyBtn.innerHTML = "✓ Copied";
        copyBtn.classList.add("success");
        setTimeout(() => {
          copyBtn.innerHTML = "📋 Copy";
          copyBtn.classList.remove("success");
        }, 2000);
      }
    });

    const regenerateBtn = document.createElement("button");
    regenerateBtn.className = "messageActionBtn";
    regenerateBtn.innerHTML = "🔄 Regenerate";
    regenerateBtn.title = "Regenerate response";
    regenerateBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      // Find the previous user message
      const allBubbles = Array.from(messages.children);
      const currentIndex = allBubbles.indexOf(bubble);
      for (let i = currentIndex - 1; i >= 0; i--) {
        if (allBubbles[i].classList.contains("user")) {
          const userText = allBubbles[i].querySelector(".msg")?.textContent || "";
          if (userText) {
            // Remove this assistant message and all messages after it
            for (let j = currentIndex; j < allBubbles.length; j++) {
              allBubbles[j].remove();
            }
            // Update query context
            const removedCount = allBubbles.length - currentIndex;
            queryContext = queryContext.slice(0, -removedCount * 2);
            // Set user input and send
            userInput.value = userText;
            sendMessage();
            break;
          }
        }
      }
    });

    messageActions.appendChild(copyBtn);
    messageActions.appendChild(regenerateBtn);
  }

  meta.appendChild(metaLeft);
  meta.appendChild(messageActions);
  meta.appendChild(metaRight);

  const pre = document.createElement("pre");
  pre.className = "msg";
  if (thinking) {
    pre.innerHTML = '<span class="thinking">Thinking</span>';
  } else {
    if (useTypewriter && text && role === "assistant") {
      // Start typewriter effect
      typewriterEffect(messages, pre as HTMLElement, text);
    } else {
      pre.textContent = text || "";
    }
  }

  bubble.appendChild(meta);
  bubble.appendChild(pre);

  if (role === "assistant") {
    renderSourcesProgress(bubble, sources || []);
    renderSourcesDetails(bubble, sources || [], { includeIndex: false });
  }

  if (role === "assistant") {
    if (querys && querys.length) {
      const d = document.createElement("details");
      d.innerHTML = `<summary>Queries (${querys.length})</summary><pre style="padding:8px;white-space:pre-wrap;font-size:0.9em;max-height:200px;overflow:auto">${querys
        .map((q, i) => `${i ? "Expanded " + i : "Original"}: ${q}`)
        .join("\n")}</pre>`;
      bubble.appendChild(d);
    }
    if (prompt) {
      const d = document.createElement("details");
      d.innerHTML = `<summary>Prompt</summary><pre style="padding:8px;white-space:pre-wrap;font-size:0.85em;max-height:400px;overflow:auto;background:#f5f5f5">${prompt}</pre>`;
      bubble.appendChild(d);
    }
  }

  messages.appendChild(bubble);
  messages.scrollTop = messages.scrollHeight;
  return bubble;
}

// Read runtime settings from form controls and clamp values to backend-supported ranges.
function getSettingsFromUI(): RAGSettings {
  // Clamp values to valid ranges
  const chunkKValue = Number(chunkK.value || 10);
  const queryExpandKValue = Number(queryExpandK.value || 1);

  return {
    cloudBase: cloudBase.value.trim(),
    authToken: getAuthToken(),
    titleK: Number(titleK.value || 3),
    chunkK: Math.max(1, Math.min(12, chunkKValue)),
    queryExpandK: Math.max(1, Math.min(3, queryExpandKValue)),
    chunkIndex: chunkIndex.value.trim() || null,
  };
}

// Hydrate form controls from persisted settings so the UI mirrors the effective request config.
function applySettingsToUI(s: Partial<RAGSettings>): void {
  cloudBase.value = s.cloudBase ?? "";
  titleK.value = String(Number.isFinite(s.titleK) ? s.titleK : 3);
  chunkK.value = String(Number.isFinite(s.chunkK) ? s.chunkK : 10);
  queryExpandK.value = String(Number.isFinite(s.queryExpandK) ? s.queryExpandK : 1);
  chunkIndex.value = s.chunkIndex ?? "";
}

// Load settings with defaults to keep the page usable even when storage is empty or invalid.
function loadSettings(): RAGSettings {
  const defaults: RAGSettings = {
    cloudBase: "https://us-central1-xixibaigao.cloudfunctions.net/chatbot-milesguo/chatbot_stream",
    titleK: 3,
    chunkK: 10,
    queryExpandK: 1,
    chunkIndex: "miles_guo",
    authToken: "",
  };
  return loadSettingsFromStorage<RAGSettings>(STORAGE_KEY, defaults);
}

// Persist validated settings so repeated sessions do not require manual reconfiguration.
function saveSettings(s: RAGSettings): void {
  saveSettingsToStorage(STORAGE_KEY, s);
}

let inFlight: AbortController | null = null;
let currentThinkingBubble: HTMLElement | null = null;
let rateLimit: ReturnType<typeof createRateLimitController>;
// Store conversation history for query_context
let queryContext: string[] = [];

// Orchestrate one chat turn end-to-end, including cancellation, auth, request dispatch, and UI updates.
async function sendMessage(): Promise<void> {
  const text = userInput.value.trim();
  if (!text) return;
  errorLine.textContent = "";

  // Keep one active request to prevent mixed responses updating the same conversation state.
  // Cancel previous request if in flight
  if (inFlight) {
    inFlight.abort();
    inFlight = null;
    // Mark previous thinking bubble as cancelled
    if (currentThinkingBubble) {
      const msgElement = currentThinkingBubble.querySelector(".msg");
      if (msgElement) {
        msgElement.textContent = "(Cancelled)";
        msgElement.classList.remove("typing");
      }
      const statusIndicator = currentThinkingBubble.querySelector(".progressIndicator");
      if (statusIndicator) {
        statusIndicator.innerHTML = `
          <div class="progressDot"></div>
          <span class="progressText">Cancelled</span>
        `;
      }
      currentThinkingBubble = null;
    }
  }

  // Ensure token is fetched before sending request
  if (!getAuthToken()) {
    const fetchedToken = await fetchAuthTokenFromBackend(cloudBase.value);
    if (!fetchedToken && !getAuthToken()) {
      // If no token from URL param and fetch returned null, warn user
      console.warn("No authentication token available. Backend may require authentication.");
    }
  }

  const s = getSettingsFromUI();
  const endpoint = buildEndpointUrl(s.cloudBase);
  if (!endpoint) {
    errorLine.textContent = "Please fill Cloud Functions URL.";
    return;
  }
  if (!s.chunkIndex) {
    errorLine.textContent = "Please fill chunk_index (e.g. miles_guo).";
    setStatus(statusPill, "Missing chunk_index", true);
    return;
  }

  // Validate URL format
  try {
    new URL(endpoint);
  } catch (e) {
    errorLine.textContent = "Invalid URL format. Please enter a valid Cloud Functions URL.";
    setStatus(statusPill, "Invalid URL", true);
    return;
  }

  addMessage({ role: "user", text });
  userInput.value = "";

  // Determine if we should use streaming endpoint
  // Only use streaming if the URL explicitly contains /chatbot_stream
  // User must explicitly specify streaming endpoint in the URL
  let useStreaming = false;

  // Check if URL explicitly contains streaming endpoint
  if (endpoint.includes("/chatbot_stream")) {
    useStreaming = true;
  }

  // Use the full URL directly (user can specify complete endpoint like /chatbot or /chatbot_stream)
  const url = new URL(endpoint);
  url.searchParams.set("txt_query", text);
  url.searchParams.set("title_k", String(s.titleK));
  url.searchParams.set("chunk_k", String(s.chunkK));
  url.searchParams.set("query_expand_k", String(s.queryExpandK));
  // chunk_index is required by backend and validated above.
  url.searchParams.set("chunk_index", s.chunkIndex);
  // Query context is intentionally short to balance continuity and URL length constraints.
  // Add query_context if available
  if (queryContext && queryContext.length > 0) {
    for (const contextItem of queryContext) {
      url.searchParams.append("query_context", contextItem);
    }
  }

  const controller = new AbortController();
  inFlight = controller;

  rateLimit.clear();
  sendBtn.disabled = true;
  cancelBtn.disabled = false;
  setStatus(statusPill, "Requesting…");

  // Add thinking indicator for assistant with enhanced status
  const thinkingBubble = addMessage({ role: "assistant", thinking: true });
  currentThinkingBubble = thinkingBubble;

  // Add status indicator to thinking bubble
  const statusIndicator = document.createElement("div");
  statusIndicator.className = "progressIndicator";
  statusIndicator.innerHTML = `
    <div class="progressDot"></div>
    <span class="progressText">${useStreaming ? "Connecting to stream..." : "Searching knowledge base..."}</span>
  `;
  thinkingBubble.appendChild(statusIndicator);

  try {
    // Get fresh token in case it was just fetched
    const authToken = getAuthToken();
    const headers: Record<string, string> = {
      Accept: useStreaming ? "text/event-stream" : "application/json",
    };

    // Always include Authorization header if token exists
    if (authToken) {
      headers.Authorization = `Bearer ${authToken}`;
      console.log("Sending request with Authorization header");
    } else {
      console.warn("No auth token available - request may fail if backend requires authentication");
    }

    if (useStreaming) {
      // Use streaming response with EventSource-like handling
      await handleStreamingResponse(url.toString(), headers, controller, thinkingBubble, text);
    } else {
      // Use regular non-streaming response
      await handleNonStreamingResponse(url.toString(), headers, controller, thinkingBubble, text);
    }
  } catch (e) {
    // Only show error if not cancelled (cancelled requests are already handled above)
    const error = e as Error;
    if (error?.name !== "AbortError" || thinkingBubble === currentThinkingBubble) {
      const msg = error?.name === "AbortError" ? "Request cancelled." : String(error?.message || e);
      addMessage({ role: "assistant", text: `Error: ${msg}`, updateBubble: thinkingBubble, useTypewriter: false });
      setStatus(statusPill, "Error", true);
      errorLine.textContent = msg;
    }
  } finally {
    inFlight = null;
    currentThinkingBubble = null;
    // If we are counting down for rate limiting, keep send disabled.
    if (!rateLimit.isActive()) sendBtn.disabled = false;
    cancelBtn.disabled = true;
  }
}

// Consume SSE responses incrementally to stream assistant text and attach final retrieval metadata.
async function handleStreamingResponse(
  url: string,
  headers: Record<string, string>,
  controller: AbortController,
  thinkingBubble: HTMLElement,
  userText: string
): Promise<void> {
  const res = await fetch(url, {
    method: "GET",
    signal: controller.signal,
    headers: headers,
  });

  if (!res.ok) {
    if (res.status === 401) {
      const tokenInfo = headers.Authorization ? "Token is present but invalid" : "No token provided";
      throw new Error(`Unauthorized (401). ${tokenInfo}. Check API_AUTH_TOKEN environment variable on backend or include token in URL parameter: ?token=xxx`);
    }
    if (res.status === 429) {
      const retryAfterHeader = res.headers.get("Retry-After");
      const retryAfter = Number(retryAfterHeader || "");
      if (Number.isFinite(retryAfter) && retryAfter > 0) {
        rateLimit.start(retryAfter);
        throw new Error(`Rate limit exceeded (429). Retry after ${retryAfter}s.`);
      }
      throw new Error("Rate limit exceeded (429). Please retry later.");
    }
    const detail = await res.text().catch(() => `HTTP ${res.status}`);
    throw new Error(detail);
  }

  const reader = res.body?.getReader();
  if (!reader) {
    throw new Error("Response body is not readable");
  }

  // Preserve partial SSE frames in `buffer` because network chunks may split event boundaries.
  const decoder = new TextDecoder();
  let buffer = "";
  let fullContent = "";
  let sources: Source[] | null = null;
  let prompt: string | null = null;
  let querys: string[] | null = null;

  // Get the message element for streaming updates
  const msgElement = thinkingBubble.querySelector(".msg");
  if (!msgElement) {
    throw new Error("Message element not found");
  }

  // Remove thinking indicator and prepare for streaming
  msgElement.innerHTML = "";
  msgElement.classList.remove("typing");
  msgElement.classList.add("typing");

  // Update status to show streaming
  const statusIndicator = thinkingBubble.querySelector(".progressIndicator");
  if (statusIndicator) {
    statusIndicator.innerHTML = `
      <div class="progressDot"></div>
      <span class="progressText">Generating response...</span>
    `;
  }

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n\n");
      buffer = lines.pop() || ""; // Keep incomplete line in buffer

      for (const line of lines) {
        if (!line.trim()) continue; // Skip empty lines
        if (line.startsWith("data: ")) {
          try {
            const jsonStr = line.slice(6).trim();
            if (!jsonStr) continue; // Skip empty data lines
            const data: SSEChunk = JSON.parse(jsonStr);
            const { type, data: chunkData } = data;

            if (type === "content") {
              // Stream content chunks only
              if (typeof chunkData === "string") {
                fullContent += chunkData;
                msgElement.textContent = fullContent;
                messages.scrollTop = messages.scrollHeight;
              }
            } else if (type === "done") {
              // Trust terminal payload as source of truth for final content/metadata.
              // Final update with all data
              if (typeof chunkData === "object" && chunkData !== null) {
                fullContent = chunkData.content || fullContent;
                sources = chunkData.search_results || sources || [];
                prompt = chunkData.prompt || prompt;
                querys = chunkData.querys || querys;
              }
              break;
            } else if (type === "error") {
              if (typeof chunkData === "object" && chunkData !== null && "error" in chunkData) {
                throw new Error(chunkData.error || "Unknown error");
              }
              throw new Error("Unknown error");
            }
          } catch (e) {
            console.error("Error parsing SSE data:", e, line);
          }
        }
      }
    }

    // Remove typing cursor
    msgElement.classList.remove("typing");

    // Update message with final content and sources
    addMessage({
      role: "assistant",
      text: fullContent,
      sources,
      prompt,
      querys,
      updateBubble: thinkingBubble,
      useTypewriter: false, // Already displayed via streaming
    });

    // Bound context growth to keep requests predictable over long sessions.
    // Keep the last 3 Q&A pairs (6 messages) for context
    queryContext.push(`用户: ${userText}`, `助手: ${fullContent}`);
    if (queryContext.length > 6) {
      queryContext = queryContext.slice(-6);
    }
    setStatus(statusPill, "Done");
  } catch (e) {
    msgElement.classList.remove("typing");
    throw e;
  }
}

// Handle JSON responses in non-streaming mode while applying the same error and context policies.
async function handleNonStreamingResponse(
  url: string,
  headers: Record<string, string>,
  controller: AbortController,
  thinkingBubble: HTMLElement,
  userText: string
): Promise<void> {
  const res = await fetch(url, {
    method: "GET",
    signal: controller.signal,
    headers: headers,
  });

  const retryAfterHeader = res.headers.get("Retry-After");
  const raw = await res.text();
  let data: RAGResponse | null = null;
  try {
    data = raw ? JSON.parse(raw) : null;
  } catch {
    data = null;
  }

  if (!res.ok) {
    if (res.status === 401) {
      const tokenInfo = headers.Authorization ? "Token is present but invalid" : "No token provided";
      throw new Error(`Unauthorized (401). ${tokenInfo}. Check API_AUTH_TOKEN environment variable on backend or include token in URL parameter: ?token=xxx`);
    }
    if (res.status === 429) {
      const retryAfter = Number(retryAfterHeader || "");
      if (Number.isFinite(retryAfter) && retryAfter > 0) {
        rateLimit.start(retryAfter);
        throw new Error(`Rate limit exceeded (429). Retry after ${retryAfter}s.`);
      }
      throw new Error("Rate limit exceeded (429). Please retry later.");
    }
    const detail = (data as { detail?: string })?.detail || raw || `HTTP ${res.status}`;
    throw new Error(detail);
  }

  const content = data?.content ?? "";
  const sources = Array.isArray(data?.search_results) ? data.search_results : [];
  const prompt = data?.prompt ?? null;
  const querys = Array.isArray(data?.querys) ? data.querys : null;

  addMessage({
    role: "assistant",
    text: content,
    sources,
    prompt,
    querys,
    updateBubble: thinkingBubble,
    useTypewriter: true,
  });

  // Match the same retention window used in streaming mode.
  // Keep the last 3 Q&A pairs (6 messages) for context
  queryContext.push(`用户: ${userText}`, `助手: ${content}`);
  // Keep only the last 6 messages (3 rounds of Q&A)
  if (queryContext.length > 6) {
    queryContext = queryContext.slice(-6);
  }
  setStatus(statusPill, "Done");
}

// Wire up UI
cloudBase = document.getElementById("cloudBase") as HTMLInputElement;
titleK = document.getElementById("titleK") as HTMLInputElement;
chunkK = document.getElementById("chunkK") as HTMLInputElement;
queryExpandK = document.getElementById("queryExpandK") as HTMLInputElement;
chunkIndex = document.getElementById("chunkIndex") as HTMLInputElement;
statusPill = document.getElementById("statusPill") as HTMLElement;
saveBtn = document.getElementById("saveBtn") as HTMLButtonElement;
resetBtn = document.getElementById("resetBtn") as HTMLButtonElement;
clearBtn = document.getElementById("clearBtn") as HTMLButtonElement;
showSources = document.getElementById("showSources") as HTMLInputElement;
messages = document.getElementById("messages") as HTMLElement;
userInput = document.getElementById("userInput") as HTMLTextAreaElement;
sendBtn = document.getElementById("sendBtn") as HTMLButtonElement;
cancelBtn = document.getElementById("cancelBtn") as HTMLButtonElement;
errorLine = document.getElementById("errorLine") as HTMLElement;

// Keep numeric settings in a safe backend-supported range.
bindClampedNumberInput(chunkK, 1, 12);
bindClampedNumberInput(queryExpandK, 1, 3);
rateLimit = createRateLimitController(sendBtn, (text, isError = false) => setStatus(statusPill, text, isError));

// Auto-fetch token when base URL changes
cloudBase.addEventListener("change", () => {
  clearTokenCache();
  fetchAuthTokenFromBackend(cloudBase.value);
});

saveBtn.addEventListener("click", () => {
  const s = getSettingsFromUI();
  saveSettings(s);
  setStatus(statusPill, "Saved");
  setTimeout(() => setStatus(statusPill, "Idle"), 800);
});

resetBtn.addEventListener("click", () => {
  localStorage.removeItem(STORAGE_KEY);
  applySettingsToUI(loadSettings());
  setStatus(statusPill, "Reset");
  setTimeout(() => setStatus(statusPill, "Idle"), 800);
});

clearBtn.addEventListener("click", () => {
  messages.innerHTML = "";
  errorLine.textContent = "";
  queryContext = [];
  setStatus(statusPill, "Cleared");
  setTimeout(() => setStatus(statusPill, "Idle"), 800);
});

sendBtn.addEventListener("click", sendMessage);
cancelBtn.addEventListener("click", () => {
  if (inFlight) {
    inFlight.abort();
    inFlight = null;
    // Mark thinking bubble as cancelled
    if (currentThinkingBubble) {
      const msgElement = currentThinkingBubble.querySelector(".msg");
      if (msgElement) {
        msgElement.textContent = "(Cancelled)";
        msgElement.classList.remove("typing");
      }
      const statusIndicator = currentThinkingBubble.querySelector(".progressIndicator");
      if (statusIndicator) {
        statusIndicator.innerHTML = `
          <div class="progressDot"></div>
          <span class="progressText">Cancelled</span>
        `;
      }
      currentThinkingBubble = null;
    }
  }
});

userInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

// Init
applySettingsToUI(loadSettings());
setStatus(statusPill, "Idle");
// Auto-fetch auth token from backend on page load
fetchAuthTokenFromBackend(cloudBase.value);
addMessage({
  role: "assistant",
  text: "请提问",
});

