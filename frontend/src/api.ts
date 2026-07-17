// Thin API client for the InjectionRange backend.

export interface Citation {
  chunk_id: string;
  document_id: string;
  filename: string;
  section_path: string;
  score: number;
}

export interface ChatResponse {
  answer: string;
  mode: string;
  conversation_id: string;
  retrieved_chunk_ids: string[];
  citations: Citation[];
  confidence: number;
  grounded: boolean;
  token_usage: Record<string, number>;
}

export interface SearchResult {
  chunk_id: string;
  document_id: string;
  filename: string;
  section_path: string;
  content: string;
  corpus_label: string;
  dense_score: number;
  bm25_score: number;
  rrf_score: number;
  rerank_score: number;
}

let token: string | null = localStorage.getItem("ir_token");

function headers(json = true): Record<string, string> {
  const h: Record<string, string> = {};
  if (json) h["Content-Type"] = "application/json";
  if (token) h["Authorization"] = `Bearer ${token}`;
  return h;
}

export async function login(email: string, password: string): Promise<void> {
  const r = await fetch("/api/auth/login", {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ email, password }),
  });
  if (!r.ok) throw new Error("login failed");
  token = (await r.json()).access_token;
  localStorage.setItem("ir_token", token!);
}

export const loggedIn = () => !!token;

export async function chat(message: string, conversationId?: string): Promise<ChatResponse> {
  const r = await fetch("/api/chat", {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ message, conversation_id: conversationId ?? null }),
  });
  return r.json();
}

export async function search(query: string): Promise<{ mode: string; results: SearchResult[] }> {
  const r = await fetch("/api/search", {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ query, top_k: 25 }),
  });
  return r.json();
}

export async function listDocuments() {
  return (await fetch("/api/documents", { headers: headers() })).json();
}

export async function uploadDocument(file: File, corpusLabel: string) {
  const fd = new FormData();
  fd.append("file", file);
  fd.append("corpus_label", corpusLabel);
  const r = await fetch("/api/documents/upload", { method: "POST", headers: headers(false), body: fd });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getStats() {
  return (await fetch("/api/stats", { headers: headers() })).json();
}

export async function getSecurityMode() {
  return (await fetch("/api/admin/security-mode", { headers: headers() })).json();
}

export async function setSecurityMode(mode: "naive" | "hardened") {
  const r = await fetch("/api/admin/security-mode", {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ mode }),
  });
  if (!r.ok) throw new Error("toggle failed (admin login required)");
  return r.json();
}

export async function runEval() {
  return (await fetch("/api/eval/run", { method: "POST", headers: headers() })).json();
}
