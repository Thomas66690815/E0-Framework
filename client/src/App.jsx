import { useState, useEffect } from 'react';
import GraphView from './components/GraphView';
import { useSession } from './hooks/useSession';
import { useWebSocket } from './hooks/useWebSocket';
import * as api from './api';
import './styles/app.css';

/**
 * E₀ UI — Keimzelle.
 *
 * The graph IS the interface.
 * One screen: toolbar → graph → status line.
 * Everything else emerges from here.
 */
export default function App() {
  const {
    session,
    history,
    error,
    running,
    create,
    start,
    step,
    autoRun,
    stopAutoRun,
    handleWsEvent,
    setError,
  } = useSession();

  const [snapshot, setSnapshot] = useState(null);
  const [backendOk, setBackendOk] = useState(null);
  const [field, setField] = useState('trace_quality');

  useWebSocket(session?.session_id, handleWsEvent);

  // Health check
  useEffect(() => {
    api.getHealth()
      .then(() => setBackendOk(true))
      .catch(() => setBackendOk(false));
  }, []);

  // Fetch snapshot after session or history changes
  useEffect(() => {
    if (!session?.session_id) { setSnapshot(null); return; }
    api.getSnapshot(session.session_id)
      .then(setSnapshot)
      .catch(() => {});
  }, [session?.session_id, history.length]);

  // Landscape states for node selection
  const states = snapshot?.landscape?.states || [];

  // ── Handlers ──────────────────────────────
  const handleLoad = async () => {
    await create('json', { spec: DEFAULT_SPEC });
  };

  const handleNodeClick = async (nodeId) => {
    if (!session) return;
    if (session.state === 'created') {
      // First click → start from that node
      await start(nodeId, null, 50);
    }
  };

  const handleStep = () => step();
  const handleAuto = () => running ? stopAutoRun() : autoRun(200);

  // ── Derive state labels ───────────────────
  const lastStep = history.length > 0 ? history[history.length - 1] : null;
  const canStep = session?.state === 'running' && !running;
  const canAuto = session?.state === 'running';

  // ── Compute metrics from history ──────────
  const successes = history.filter((h) => h.outcome === 'SUCCESS').length;
  const failures = history.filter((h) => h.outcome === 'FAILURE').length;
  const escalations = history.filter((h) => h.escalated).length;
  const successRate = history.length > 0 ? (successes / history.length * 100).toFixed(0) : null;

  return (
    <div className="app">
      {/* ── Toolbar ──────────────────────── */}
      <div className="toolbar">
        <span className="toolbar-title">E₀</span>

        {backendOk === false && (
          <span className="toolbar-warn">Backend offline</span>
        )}

        {!session && backendOk && (
          <button className="btn btn-primary" onClick={handleLoad}>
            Load Landscape
          </button>
        )}

        {session && (
          <>
            <span className="toolbar-state">{session.state}</span>
            {session.state === 'created' && (
              <span className="toolbar-hint">Click a node to start</span>
            )}
            {canStep && (
              <button className="btn" onClick={handleStep}>Step</button>
            )}
            {canAuto && (
              <button className="btn btn-primary" onClick={handleAuto}>
                {running ? '⏸ Stop' : '▶ Auto'}
              </button>
            )}
          </>
        )}

        <span className="toolbar-spacer" />

        <label className="toolbar-field">
          Field:
          <select value={field} onChange={(e) => setField(e.target.value)}>
            <option value="trace_quality">trace_quality (q)</option>
            <option value="trace_load">trace_load (m)</option>
            <option value="S_eff">S_eff</option>
            <option value="R_eff">R_eff</option>
            <option value="delta_H">δ_H</option>
            <option value="coherence">coherence</option>
            <option value="inertia">inertia</option>
          </select>
        </label>
      </div>

      {/* ── Error ────────────────────────── */}
      {error && (
        <div className="error-bar" onClick={() => setError(null)}>
          {error}
          <span className="error-dismiss">✕</span>
        </div>
      )}

      {/* ── Graph (the entire interface) ── */}
      <GraphView
        snapshot={snapshot}
        session={session}
        history={history}
        field={field}
        onNodeClick={handleNodeClick}
      />

      {/* ── Status line ──────────────────── */}
      {lastStep && (
        <div className="status-line">
          <span className="status-tau">τ={lastStep.tau}</span>
          <span className="status-edge">{lastStep.source} → {lastStep.target}</span>
          <span className={`status-outcome ${lastStep.outcome?.toLowerCase()}`}>
            {lastStep.outcome}
          </span>
          <span className="status-count">{history.length} steps</span>
          {successRate !== null && (
            <span className="status-metrics">
              {successRate}% ok · {failures} fail · {escalations} esc
            </span>
          )}
        </div>
      )}
    </div>
  );
}

const DEFAULT_SPEC = {
  nodes: ['A', 'B', 'C', 'D', 'E'],
  edges: [
    { from: 'A', to: 'B', delta: 0.5, resistance: 1.0 },
    { from: 'A', to: 'C', delta: 0.3, resistance: 1.5 },
    { from: 'B', to: 'D', delta: 0.4, resistance: 1.0 },
    { from: 'C', to: 'D', delta: 0.6, resistance: 0.8 },
    { from: 'D', to: 'E', delta: 0.5, resistance: 1.0 },
  ],
};
