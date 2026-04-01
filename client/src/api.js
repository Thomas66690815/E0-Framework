/**
 * E₀ API client — REST + WebSocket.
 *
 * All REST calls go through the Vite proxy (see vite.config.js).
 * WebSocket connects directly to the FastAPI server.
 */

const BASE = '';  // Vite proxy handles routing

// ── REST helpers ────────────────────────────────────────

async function request(method, path, body) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(`${BASE}${path}`, opts);
  if (res.status === 204) return null;
  const data = await res.json();
  if (!res.ok) throw new APIError(res.status, data.detail || JSON.stringify(data));
  return data;
}

export class APIError extends Error {
  constructor(status, detail) {
    super(`${status}: ${detail}`);
    this.status = status;
    this.detail = detail;
  }
}

// ── Sessions ────────────────────────────────────────────

export async function createSession(mode, opts = {}) {
  return request('POST', '/sessions', { mode, ...opts });
}

export async function listSessions() {
  return request('GET', '/sessions');
}

export async function getSession(id) {
  return request('GET', `/sessions/${encodeURIComponent(id)}`);
}

export async function deleteSession(id) {
  return request('DELETE', `/sessions/${encodeURIComponent(id)}`);
}

// ── Lifecycle ───────────────────────────────────────────

export async function startSession(id, start, goal, maxCycles = 50) {
  return request('POST', `/sessions/${encodeURIComponent(id)}/start`, {
    start,
    goal: goal || null,
    max_cycles: maxCycles,
  });
}

export async function pauseSession(id) {
  return request('POST', `/sessions/${encodeURIComponent(id)}/pause`);
}

export async function resumeSession(id) {
  return request('POST', `/sessions/${encodeURIComponent(id)}/resume`);
}

export async function stepSession(id) {
  return request('POST', `/sessions/${encodeURIComponent(id)}/step`);
}

// ── Data retrieval ──────────────────────────────────────

export async function getHistory(id) {
  return request('GET', `/sessions/${encodeURIComponent(id)}/history`);
}

export async function getStrategy(id) {
  return request('GET', `/sessions/${encodeURIComponent(id)}/strategy`);
}

export async function getSnapshot(id) {
  return request('GET', `/sessions/${encodeURIComponent(id)}/snapshot`);
}

// ── Canons ──────────────────────────────────────────────

export async function listCanons() {
  return request('GET', '/canons');
}

export async function getCanon(name) {
  return request('GET', `/canons/${encodeURIComponent(name)}`);
}

// ── Health ──────────────────────────────────────────────

export async function getHealth() {
  return request('GET', '/health');
}

// ── Tests ───────────────────────────────────────────────

export async function listTests() {
  return request('GET', '/tests');
}

export async function runTest(name) {
  return request('POST', `/tests/${encodeURIComponent(name)}/run`);
}

// ── WebSocket ───────────────────────────────────────────

export function connectWebSocket(sessionId, { onEvent, onError, onClose }) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  const url = `${protocol}//${host}/sessions/${encodeURIComponent(sessionId)}/ws`;

  const ws = new WebSocket(url);

  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      onEvent?.(msg);
    } catch (err) {
      onError?.(err);
    }
  };

  ws.onerror = (e) => onError?.(e);
  ws.onclose = (e) => onClose?.(e);

  return {
    send(event, data) {
      ws.send(JSON.stringify({ event, data }));
    },
    sendPeerResponse(target) {
      ws.send(JSON.stringify({ event: 'peer_response', data: { target } }));
    },
    pause() {
      ws.send(JSON.stringify({ event: 'pause' }));
    },
    resume() {
      ws.send(JSON.stringify({ event: 'resume' }));
    },
    close() {
      ws.close();
    },
    get readyState() {
      return ws.readyState;
    },
  };
}
