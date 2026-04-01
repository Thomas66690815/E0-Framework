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
    peerRequest,
    error,
    running,
    create,
    start,
    step,
    autoRun,
    stopAutoRun,
    setSpeed,
    clearPeerRequest,
    handleWsEvent,
    setError,
  } = useSession();

  const [snapshot, setSnapshot] = useState(null);
  const [backendOk, setBackendOk] = useState(null);
  const [field, setField] = useState('trace_quality');
  const [speedMs, setSpeedMs] = useState(400);
  const [scenario, setScenario] = useState('greedy_trap');
  const [goalNode, setGoalNode] = useState(null);

  const ws = useWebSocket(session?.session_id, handleWsEvent);

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
    const sc = SCENARIOS[scenario];
    if (!sc) return;
    setGoalNode(sc.goal || null);
    await create('json', {
      spec: sc.spec,
      controller_kwargs: {
        hybrid_mode: 'AMPLITUDE_ON_DISAGREE',
        focus_k: 3,
      },
    });
  };

  const handleNodeClick = async (nodeId) => {
    if (!session) return;
    if (peerRequest) {
      // Zentrale: human chooses a candidate
      if (peerRequest.neighbors?.includes(nodeId)) {
        ws.sendPeerResponse(nodeId);
        clearPeerRequest();
      }
      return;
    }
    if (session.state === 'created') {
      // First click → start from that node, use scenario goal
      const sc = SCENARIOS[scenario];
      const goal = goalNode || sc?.goal || null;
      await start(nodeId, goal, 50);
    }
  };

  const handleStep = () => step();
  const handleAuto = () => running ? stopAutoRun() : autoRun(speedMs);
  const handleSpeedChange = (e) => {
    const ms = Number(e.target.value);
    setSpeedMs(ms);
    setSpeed(ms);
  };

  // ── Derive state labels ───────────────────
  const lastStep = history.length > 0 ? history[history.length - 1] : null;
  const isWaiting = !!peerRequest;
  const canStep = session?.state === 'running' && !running && !isWaiting;
  const canAuto = session?.state === 'running' && !isWaiting;

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
          <>
            <select
              className="toolbar-scenario"
              value={scenario}
              onChange={(e) => setScenario(e.target.value)}
            >
              {Object.entries(SCENARIOS).map(([key, sc]) => (
                <option key={key} value={key}>{sc.label}</option>
              ))}
            </select>
            <button className="btn btn-primary" onClick={handleLoad}>
              Load
            </button>
          </>
        )}

        {session && (
          <>
            <span className="toolbar-state">{isWaiting ? 'WAITING PEER' : session.state}</span>
            {session.state === 'created' && (
              <span className="toolbar-hint">
                Click a node to start{goalNode ? ` (goal: ${goalNode})` : ''}
              </span>
            )}
            {canStep && (
              <button className="btn" onClick={handleStep}>Step</button>
            )}
            {canAuto && (
              <button className="btn btn-primary" onClick={handleAuto}>
                {running ? '⏸ Stop' : '▶ Auto'}
              </button>
            )}
            {canAuto && (
              <label className="toolbar-speed">
                <input
                  type="range"
                  min="50"
                  max="2000"
                  step="50"
                  value={speedMs}
                  onChange={handleSpeedChange}
                />
                <span>{speedMs}ms</span>
              </label>
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
        goalNode={goalNode}
        peerRequest={peerRequest}
        onNodeClick={handleNodeClick}
        onPeerRespond={(target) => {
          ws.sendPeerResponse(target);
          clearPeerRequest();
        }}
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

// ── Built-in scenarios ──────────────────────────────────

const SCENARIOS = {
  diamond: {
    label: 'Diamond (5 nodes)',
    start: 'A',
    goal: 'E',
    spec: DEFAULT_SPEC,
  },
  greedy_trap: {
    label: 'Greedy Trap',
    desc: 'A↔C loop traps greedy; amplitude finds A→B→E→G→GOAL',
    start: 'A',
    goal: 'GOAL',
    spec: {
      nodes: ['A', 'B', 'C', 'E', 'G', 'GOAL'],
      edges: [
        { from: 'A', to: 'C', delta: 1.0, resistance: 0.3 },
        { from: 'C', to: 'A', delta: 1.0, resistance: 0.3 },
        { from: 'A', to: 'B', delta: 1.0, resistance: 0.8 },
        { from: 'B', to: 'E', delta: 1.0, resistance: 0.5 },
        { from: 'E', to: 'G', delta: 1.0, resistance: 0.5 },
        { from: 'G', to: 'GOAL', delta: 1.0, resistance: 0.3 },
      ],
    },
  },
  gordian: {
    label: 'Gordian Knot',
    desc: 'Decoy A: destructive interference (ΔΘ≈π). Detour B: coherent.',
    start: 'START',
    goal: 'GOAL',
    spec: {
      nodes: ['START', 'A1', 'A2', 'L1', 'L2', 'L3', 'B1', 'B2', 'GOAL'],
      edges: [
        { from: 'START', to: 'A1', delta: 0.3, resistance: 0.3 },
        { from: 'A1', to: 'A2', delta: 0.08, resistance: 0.3 },
        { from: 'A2', to: 'GOAL', delta: 0.08, resistance: 0.3 },
        { from: 'A1', to: 'L1', delta: 2.5, resistance: 0.1 },
        { from: 'L1', to: 'L2', delta: 2.5, resistance: 0.1 },
        { from: 'L2', to: 'L3', delta: 2.5, resistance: 0.1 },
        { from: 'L3', to: 'GOAL', delta: 2.5, resistance: 0.1 },
        { from: 'START', to: 'B1', delta: 0.5, resistance: 0.4 },
        { from: 'B1', to: 'B2', delta: 0.3, resistance: 0.35 },
        { from: 'B2', to: 'GOAL', delta: 0.3, resistance: 0.3 },
      ],
    },
  },
  amplitude_web: {
    label: 'Amplitude Web (8 nodes)',
    desc: 'Multi-path interference with branching and reconvergence.',
    start: 'A',
    goal: 'GOAL',
    spec: {
      nodes: ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'GOAL'],
      edges: [
        { from: 'A', to: 'B', delta: 0.5, resistance: 1.0 },
        { from: 'A', to: 'C', delta: 0.4, resistance: 0.8 },
        { from: 'C', to: 'A', delta: 0.4, resistance: 0.8 },
        { from: 'C', to: 'D', delta: 0.7, resistance: 3.0 },
        { from: 'B', to: 'E', delta: 0.3, resistance: 0.8 },
        { from: 'B', to: 'D', delta: 0.6, resistance: 1.5 },
        { from: 'E', to: 'F', delta: 0.4, resistance: 1.2 },
        { from: 'E', to: 'G', delta: 0.2, resistance: 0.5 },
        { from: 'F', to: 'G', delta: 0.3, resistance: 1.0 },
        { from: 'G', to: 'GOAL', delta: 0.1, resistance: 0.3 },
      ],
    },
  },
  multigoal: {
    label: 'Multi-Goal Gordian',
    desc: 'Two goals: GOAL (interference trap) + GOAL2 (coherent alternatives).',
    start: 'START',
    goal: 'GOAL',
    spec: {
      nodes: ['START', 'A1', 'A2', 'L1', 'L2', 'L3', 'B1', 'B2', 'D1', 'C1', 'C2', 'GOAL', 'GOAL2'],
      edges: [
        { from: 'START', to: 'A1', delta: 0.3, resistance: 0.3 },
        { from: 'A1', to: 'A2', delta: 0.4, resistance: 0.3 },
        { from: 'A2', to: 'GOAL', delta: 0.4, resistance: 0.3 },
        { from: 'A1', to: 'L1', delta: 2.0, resistance: 0.05 },
        { from: 'L1', to: 'L2', delta: 2.0, resistance: 0.05 },
        { from: 'L2', to: 'L3', delta: 2.0, resistance: 0.05 },
        { from: 'L3', to: 'GOAL', delta: 2.0, resistance: 0.05 },
        { from: 'START', to: 'B1', delta: 0.5, resistance: 0.4 },
        { from: 'B1', to: 'B2', delta: 0.3, resistance: 0.35 },
        { from: 'B2', to: 'GOAL', delta: 0.3, resistance: 0.3 },
        { from: 'A1', to: 'D1', delta: 0.5, resistance: 0.3 },
        { from: 'D1', to: 'GOAL2', delta: 0.4, resistance: 0.3 },
        { from: 'START', to: 'C1', delta: 0.6, resistance: 0.4 },
        { from: 'C1', to: 'C2', delta: 0.4, resistance: 0.3 },
        { from: 'C2', to: 'GOAL2', delta: 0.3, resistance: 0.3 },
      ],
    },
  },
  resonator: {
    label: 'Resonator Loop',
    desc: '3-node loop A→B→C→A with leakage C→OUT. Tests coherent cycling.',
    start: 'A',
    goal: null,
    spec: {
      nodes: ['A', 'B', 'C', 'OUT'],
      edges: [
        { from: 'A', to: 'B', delta: 1.5, resistance: 0.2 },
        { from: 'B', to: 'C', delta: 1.5, resistance: 0.2 },
        { from: 'C', to: 'A', delta: 1.5, resistance: 0.2 },
        { from: 'C', to: 'OUT', delta: 0.5, resistance: 0.8 },
      ],
    },
  },
};
