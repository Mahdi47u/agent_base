export type Citation = {
  id?: string;
  title: string;
  source_url: string;
  version?: string;
  location?: string;
  excerpt?: string;
};

export type ActionProposal = {
  id: string;
  action_type: string;
  title: string;
  payload: Record<string, unknown>;
  target_key?: string;
  target_version?: string;
  status: "pending" | "executed" | "cancelled" | "expired" | "conflict" | "failed";
  expires_at: string;
  result?: Record<string, unknown>;
};

export type ToolEvent = {
  tool: string;
  tool_call_id?: string;
  status: "running" | "complete";
  duration_ms?: number;
};

export type AgentMessage = {
  id: string;
  role: "user" | "assistant" | "tool";
  content: string;
  citations: Citation[];
  metadata?: { tool_events?: ToolEvent[]; ui?: unknown[] };
  created_at: string;
};

export type AgentSession = {
  id: string;
  title: string;
  provider: string;
  model_name: string;
  context: Record<string, unknown>;
  messages: AgentMessage[];
  action_proposals: ActionProposal[];
  last_activity_at: string;
};

export type StreamEventName = "start" | "tool" | "delta" | "complete" | "error";
export type StreamEvent = { event: StreamEventName; payload: Record<string, unknown> };

let csrfToken: string | null = null;

async function getCsrfToken() {
  if (csrfToken) return csrfToken;
  const response = await fetch("/api/agent/auth/csrf/", { credentials: "include", cache: "no-store" });
  if (!response.ok) throw new Error("Could not initialize CSRF protection.");
  const data = (await response.json()) as { csrfToken: string };
  csrfToken = data.csrfToken;
  return csrfToken;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");
  if (init.method && init.method !== "GET") headers.set("X-CSRFToken", await getCsrfToken());
  const response = await fetch(path, { ...init, headers, credentials: "include", cache: "no-store" });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed (${response.status}).`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function login(username: string, password: string) {
  const result = await request<{ id: string; username: string }>("/api/agent/auth/login/", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  csrfToken = null; // Django rotates the token after login.
  return result;
}

export const me = () => request<{ id: string; username: string }>("/api/agent/auth/me/");
export async function logout() {
  await request("/api/agent/auth/logout/", { method: "POST", body: "{}" });
  csrfToken = null;
}
export const listSessions = () => request<AgentSession[]>("/api/agent/sessions/");
export const createSession = () =>
  request<AgentSession>("/api/agent/sessions/", { method: "POST", body: "{}" });
export const deleteSession = (id: string) =>
  request<void>(`/api/agent/sessions/${id}/`, { method: "DELETE" });
export const decideProposal = (id: string, decision: "confirm" | "cancel") =>
  request<ActionProposal>(`/api/agent/actions/${id}/${decision}/`, { method: "POST", body: "{}" });

export function parseSseBuffer(input: string, flush = false): { events: StreamEvent[]; remainder: string } {
  const blocks = input.replace(/\r\n/g, "\n").split("\n\n");
  const remainder = flush ? "" : (blocks.pop() ?? "");
  const events: StreamEvent[] = [];
  for (const block of blocks) {
    if (!block.trim()) continue;
    const lines = block.split("\n");
    const event = lines.find((line) => line.startsWith("event:"))?.slice(6).trim() as StreamEventName;
    const data = lines
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trimStart())
      .join("\n");
    if (event && data) events.push({ event, payload: JSON.parse(data) as Record<string, unknown> });
  }
  return { events, remainder };
}

export async function streamMessage(
  sessionId: string,
  content: string,
  onEvent: (event: StreamEventName, payload: Record<string, unknown>) => void,
  signal?: AbortSignal,
) {
  const response = await fetch(`/api/agent/sessions/${sessionId}/messages/stream/`, {
    method: "POST",
    headers: {
      Accept: "text/event-stream",
      "Content-Type": "application/json",
      "X-CSRFToken": await getCsrfToken(),
      "X-Request-ID": crypto.randomUUID(),
    },
    credentials: "include",
    body: JSON.stringify({ content, context: { pathname: window.location.pathname } }),
    signal,
  });
  if (!response.ok || !response.body) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? "The assistant connection failed.");
  }
  if (!response.headers.get("content-type")?.includes("text/event-stream")) {
    throw new Error("The server did not return an SSE stream.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let terminal = false;
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const parsed = parseSseBuffer(buffer, done);
    buffer = parsed.remainder;
    for (const item of parsed.events) {
      if (item.event === "complete" || item.event === "error") terminal = true;
      onEvent(item.event, item.payload);
    }
    if (done) break;
  }
  if (!terminal) throw new Error("The assistant stream closed before a terminal event.");
}
