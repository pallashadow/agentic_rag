// Shared frontend utilities for chatbot pages.
// Motivation: avoid duplicated logic between standard RAG and Agentic RAG UIs.
import type { TokenResponse } from "./types.js";

// Remove trailing slashes from a URL-like string.
export function trimSlash(s: string | null | undefined): string {
  return String(s || "").replace(/\/+$/, "");
}

// Normalize endpoint URL from the Cloud Functions base.
export function buildEndpointUrl(cloudBase: string | null | undefined): string {
  const url = String(cloudBase || "").trim();
  if (!url) return "";
  return trimSlash(url);
}

// Update the status pill with optional error styling.
export function setStatus(statusPill: HTMLElement, text: string, isError: boolean = false): void {
  statusPill.textContent = text;
  statusPill.classList.toggle("danger", isError);
}

// Format current time for chat message metadata.
export function nowTime(): string {
  const d = new Date();
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

// Typewriter effect for assistant messages.
export async function typewriterEffect(
  messages: HTMLElement,
  element: HTMLElement,
  text: string,
  speed: number = 20
): Promise<void> {
  element.textContent = "";
  element.classList.add("typing");

  for (let i = 0; i < text.length; i++) {
    element.textContent += text[i];
    // Scroll to bottom as content is typed
    messages.scrollTop = messages.scrollHeight;
    // Small delay between characters
    // eslint-disable-next-line no-await-in-loop
    await new Promise((resolve) => setTimeout(resolve, speed));
  }

  element.classList.remove("typing");
}

// Copy text to clipboard with a fallback for older browsers.
export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.position = "fixed";
    textArea.style.opacity = "0";
    document.body.appendChild(textArea);
    textArea.select();
    try {
      document.execCommand("copy");
      document.body.removeChild(textArea);
      return true;
    } catch {
      document.body.removeChild(textArea);
      return false;
    }
  }
}

// Shared auth token cache across pages in this frontend.
let cachedAuthToken: string | null = null;
let tokenFetchPromise: Promise<string | null> | null = null;
let cachedTokenBaseUrl: string | null = null;

// Reset token cache when backend base URL changes so stale credentials are never reused across environments.
export function clearTokenCache(): void {
  cachedAuthToken = null;
  tokenFetchPromise = null;
  cachedTokenBaseUrl = null;
}

// Fetch auth token from backend by rewriting the Cloud Functions URL path to /token.
export async function fetchAuthTokenFromBackend(baseUrlRaw: string): Promise<string | null> {
  const baseUrl = String(baseUrlRaw || "").trim();
  if (!baseUrl) {
    console.warn("Cloud Functions URL is empty.");
    return null;
  }

  // If base URL changed, reset cache.
  if (cachedTokenBaseUrl !== baseUrl) {
    clearTokenCache();
    cachedTokenBaseUrl = baseUrl;
  }

  // Reuse the same in-flight promise so quick repeated sends do not trigger duplicate token requests.
  if (tokenFetchPromise) return tokenFetchPromise;

  tokenFetchPromise = (async (): Promise<string | null> => {
    try {
      let url: URL;
      try {
        url = new URL(baseUrl);
      } catch (e) {
        console.error("Invalid Cloud Functions URL format:", e, "URL was:", baseUrl);
        return null;
      }

      let tokenUrl: string;
      try {
        const pathSegments = url.pathname.split("/").filter(Boolean);
        if (pathSegments.length > 0) {
          pathSegments[pathSegments.length - 1] = "token";
          url.pathname = "/" + pathSegments.join("/");
        } else {
          url.pathname = "/token";
        }
        tokenUrl = url.toString();
      } catch (e) {
        console.warn("Error constructing token URL:", e, "URL was:", baseUrl);
        return null;
      }

      if (!tokenUrl) {
        console.warn("Token URL is empty (check Cloud Functions URL).");
        return null;
      }

      const res = await fetch(tokenUrl, {
        method: "GET",
        headers: { Accept: "application/json" },
      });

      if (res.ok) {
        const data: TokenResponse = await res.json();
        cachedAuthToken = data.token || null;
        if (cachedAuthToken) cachedAuthToken = cachedAuthToken.trim();
        return cachedAuthToken;
      }
      console.warn(`Failed to fetch auth token: ${res.status} ${res.statusText}`);
    } catch (e) {
      console.warn("Failed to fetch auth token from backend:", e);
    }
    return null;
  })();

  return tokenFetchPromise;
}

// Get auth token from URL param or cached backend token.
export function getAuthToken(): string {
  const params = new URLSearchParams(window.location.search);
  const urlToken = params.get("token");
  // URL token wins intentionally, making one-off debugging overrides easy without code changes.
  if (urlToken) return urlToken.trim();
  return (cachedAuthToken && cachedAuthToken.trim()) || "";
}

