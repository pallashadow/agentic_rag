// Shared type definitions for the chatbot frontend

export interface Source {
  doc_title?: string;
  doc_id?: string;
  chunk_id?: string;
  text?: string;
  score?: number | string;
  index?: string;
  doc_summary?: string;
  summary?: string;
  context?: string;
}

export interface SearchOp {
  type: string;
  query?: string;
  query_list?: string[];
  doc_ids?: string[];
  doc_id?: string;
  chunk_id?: string;
  distance?: number;
  [key: string]: unknown;
}

export interface RAGSettings {
  cloudBase: string;
  authToken: string;
  titleK: number;
  chunkK: number;
  queryExpandK: number;
  chunkIndex: string | null;
}

export interface AgenticSettings extends RAGSettings {
  maxIter: number;
}

export interface MessageOptions {
  role: "user" | "assistant";
  text?: string;
  sources?: Source[] | null;
  prompt?: string | null;
  querys?: string[] | null;
  queryType?: string | null;
  searchCount?: number | null;
  historicalSearchOps?: SearchOp[] | null;
  thinking?: boolean;
  updateBubble?: HTMLElement | null;
  useTypewriter?: boolean;
}

export interface RAGResponse {
  content: string;
  search_results?: Source[];
  prompt?: string;
  querys?: string[];
}

export interface AgenticResponse {
  content: string;
  search_results?: Source[];
  query_type?: string;
  search_count?: number;
  historical_search_ops?: SearchOp[];
}

export interface SSEChunk {
  type: "content" | "done" | "error" | "status" | "content_reset";
  // A single SSE channel carries incremental text and structured terminal payloads.
  // Keeping this union explicit helps event handlers narrow safely by `type`.
  data: string | {
    content?: string;
    error?: string;
    status?: string;
    node?: string;
    iteration?: number;
    search_results?: Source[];
    query_type?: string;
    search_count?: number;
    historical_search_ops?: SearchOp[];
    prompt?: string;
    querys?: string[];
  };
}

export interface TokenResponse {
  token: string | null;
}

