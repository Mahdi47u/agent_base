"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import {
  type ActionProposal,
  type AgentSession,
  type ToolEvent,
  createSession,
  decideProposal,
  deleteSession,
  listSessions,
  login,
  logout,
  me,
  streamMessage,
} from "@/lib/agent-api";

type User = { id: string; username: string };

function Login({ onSuccess }: { onSuccess: (user: User) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      onSuccess(await login(username, password));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Sign in failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-shell">
      <form className="login-form" onSubmit={submit}>
        <div className="wordmark">Agent Base</div>
        <p className="login-copy">Sign in with the Django user you created for this environment.</p>
        <label>
          Username
          <input autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        {error ? <p className="form-error">{error}</p> : null}
        <button className="primary-button" disabled={busy || !username || !password}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </main>
  );
}

function Proposal({ proposal, onChanged }: { proposal: ActionProposal; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function decide(decision: "confirm" | "cancel") {
    setBusy(true);
    setError("");
    try {
      await decideProposal(proposal.id, decision);
      onChanged();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not update the proposal.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="proposal" aria-label="Action requires confirmation">
      <strong>{proposal.title}</strong>
      <pre>{JSON.stringify(proposal.payload, null, 2)}</pre>
      {error ? <p className="form-error">{error}</p> : null}
      <div className="button-row">
        <button className="primary-button" disabled={busy} onClick={() => decide("confirm")}>
          Confirm
        </button>
        <button className="secondary-button" disabled={busy} onClick={() => decide("cancel")}>
          Cancel
        </button>
      </div>
    </section>
  );
}

function Chat({ user, onSignedOut }: { user: User; onSignedOut: () => void }) {
  const [sessions, setSessions] = useState<AgentSession[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [draft, setDraft] = useState("");
  const [tools, setTools] = useState<ToolEvent[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const abortRef = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);

  const selected = useMemo(() => sessions.find((item) => item.id === selectedId) ?? null, [sessions, selectedId]);

  async function refresh(preferredId?: string) {
    let rows = await listSessions();
    if (!rows.length) rows = [await createSession()];
    setSessions(rows);
    setSelectedId((current) => {
      const wanted = preferredId ?? current;
      return rows.some((item) => item.id === wanted) ? wanted : rows[0].id;
    });
  }

  useEffect(() => {
    refresh()
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Could not load conversations."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [selected?.messages.length, draft, tools]);

  async function newConversation() {
    const created = await createSession();
    setSessions((current) => [created, ...current]);
    setSelectedId(created.id);
    setDraft("");
    setTools([]);
  }

  async function removeConversation(id: string) {
    await deleteSession(id);
    await refresh();
  }

  async function send(event: FormEvent) {
    event.preventDefault();
    const content = input.trim();
    if (!content || !selected || sending) return;
    setInput("");
    setDraft("");
    setTools([]);
    setError("");
    setSending(true);
    const controller = new AbortController();
    abortRef.current = controller;
    const optimistic = {
      id: crypto.randomUUID(),
      role: "user" as const,
      content,
      citations: [],
      created_at: new Date().toISOString(),
    };
    setSessions((current) =>
      current.map((item) => (item.id === selected.id ? { ...item, messages: [...item.messages, optimistic] } : item)),
    );
    try {
      await streamMessage(
        selected.id,
        content,
        (eventName, payload) => {
          if (eventName === "delta" && typeof payload.text === "string") {
            setDraft((current) => current + payload.text);
          }
          if (eventName === "tool" && typeof payload.tool === "string") {
            const incoming = payload as ToolEvent;
            setTools((current) => {
              const next = [...current];
              const index = next.findIndex((item) => item.tool_call_id === incoming.tool_call_id);
              if (index >= 0) next[index] = incoming;
              else next.push(incoming);
              return next.slice(-12);
            });
          }
          if (eventName === "error") {
            setError(typeof payload.detail === "string" ? payload.detail : "The assistant failed.");
          }
        },
        controller.signal,
      );
      await refresh(selected.id);
    } catch (reason) {
      if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "The assistant failed.");
      await refresh(selected.id).catch(() => undefined);
    } finally {
      setSending(false);
      setDraft("");
      setTools([]);
      abortRef.current = null;
    }
  }

  async function signOut() {
    await logout();
    onSignedOut();
  }

  return (
    <main className="app-shell">
      <aside className="session-sidebar">
        <div className="sidebar-top">
          <div className="wordmark">Agent Base</div>
          <button className="icon-button" onClick={newConversation} aria-label="New conversation" title="New conversation">
            +
          </button>
        </div>
        <nav aria-label="Conversations">
          {sessions.map((session) => (
            <div className={`session-row ${session.id === selectedId ? "selected" : ""}`} key={session.id}>
              <button className="session-select" onClick={() => setSelectedId(session.id)}>
                <span>{session.title}</span>
                <time>{new Date(session.last_activity_at).toLocaleDateString()}</time>
              </button>
              <button className="delete-button" onClick={() => removeConversation(session.id)} aria-label={`Delete ${session.title}`}>
                ×
              </button>
            </div>
          ))}
        </nav>
        <div className="account-row">
          <span>{user.username}</span>
          <button className="text-button" onClick={signOut}>Sign out</button>
        </div>
      </aside>

      <section className="chat-panel">
        <header className="chat-header">
          <span>{selected?.title ?? "Conversation"}</span>
          <span className="provider">{selected?.provider ?? "mock"}</span>
        </header>
        <div className="messages" aria-live="polite">
          {loading ? <p className="empty-state">Loading conversations…</p> : null}
          {!loading && selected?.messages.length === 0 ? (
            <div className="empty-state">
              <strong>Start with a real task.</strong>
              <span>Try “What tools can you use?” or “What time is it?”</span>
            </div>
          ) : null}
          {selected?.messages.filter((message) => message.role !== "tool").map((message) => (
            <article className={`message ${message.role}`} key={message.id}>
              <div className="message-author">{message.role === "user" ? "You" : "Assistant"}</div>
              <div className="message-body">{message.content}</div>
              {message.citations.length ? (
                <ul className="citations">
                  {message.citations.map((citation, index) => (
                    <li key={citation.id ?? `${citation.title}-${index}`}>
                      {citation.source_url.startsWith("http") ? (
                        <a href={citation.source_url} target="_blank" rel="noreferrer">{citation.title}</a>
                      ) : citation.title}
                      {citation.location ? ` — ${citation.location}` : ""}
                    </li>
                  ))}
                </ul>
              ) : null}
            </article>
          ))}
          {tools.length ? (
            <div className="tool-list">
              {tools.map((tool) => (
                <span key={tool.tool_call_id ?? tool.tool}>
                  {tool.status === "running" ? "Running" : "Used"} {tool.tool}
                  {tool.duration_ms !== undefined ? ` · ${tool.duration_ms} ms` : ""}
                </span>
              ))}
            </div>
          ) : null}
          {draft ? (
            <article className="message assistant">
              <div className="message-author">Assistant</div>
              <div className="message-body">{draft}</div>
            </article>
          ) : null}
          {selected?.action_proposals.map((proposal) => (
            <Proposal key={proposal.id} proposal={proposal} onChanged={() => refresh(selected.id)} />
          ))}
          {error ? <p className="stream-error">{error}</p> : null}
          <div ref={endRef} />
        </div>
        <form className="composer" onSubmit={send}>
          <textarea
            rows={2}
            placeholder="Message the assistant"
            aria-label="Message"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
          />
          {sending ? (
            <button type="button" className="secondary-button" onClick={() => abortRef.current?.abort()}>Stop</button>
          ) : (
            <button className="primary-button" disabled={!input.trim() || !selected}>Send</button>
          )}
        </form>
      </section>
    </main>
  );
}

export default function Home() {
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    me().then(setUser).catch(() => setUser(null)).finally(() => setChecking(false));
  }, []);

  if (checking) return <main className="login-shell"><p>Loading…</p></main>;
  if (!user) return <Login onSuccess={setUser} />;
  return <Chat user={user} onSignedOut={() => setUser(null)} />;
}
