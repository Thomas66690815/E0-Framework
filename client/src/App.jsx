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
  const [observing, setObserving] = useState(false);
  const [obsInfo, setObsInfo] = useState(null);

  const ws = useWebSocket(session?.session_id, handleWsEvent);

  // Health check
  useEffect(() => {
    api.getHealth()
      .then(() => setBackendOk(true))
      .catch(() => setBackendOk(false));
  }, []);

  // Fetch snapshot after session or history changes
  useEffect(() => {
    if (!session?.session_id) { setSnapshot(null); setObsInfo(null); return; }
    if (observing) {
      api.getObservation(session.session_id)
        .then((data) => { setSnapshot(data); setObsInfo(data.observation || null); })
        .catch(() => {});
    } else {
      api.getSnapshot(session.session_id)
        .then(setSnapshot)
        .catch(() => {});
      setObsInfo(null);
    }
  }, [session?.session_id, history.length, observing]);

  // Landscape states for node selection
  const states = snapshot?.landscape?.states || [];

  // ── Handlers ──────────────────────────────
  const handleLoad = async () => {
    const sc = SCENARIOS[scenario];
    if (!sc) return;
    setGoalNode(sc.goal || null);
    const kwargs = {
      hybrid_mode: 'amplitude_on_disagree',
      focus_k: 3,
    };
    if (sc.goal) {
      kwargs.hybrid_goals = [sc.goal];
      kwargs.hybrid_geometry = 'goal_reaching';
    }
    await create('json', {
      spec: sc.spec,
      controller_kwargs: kwargs,
    });
  };

  const handleNodeClick = async (nodeId) => {
    if (!session) return;
    if (observing) {
      // In observation mode: click a node to focus on it
      const obs = obsInfo;
      if (obs?.focused_node === nodeId) {
        // Already focused → defocus
        await obsNavigate('defocus');
      } else if (obs?.focused_node) {
        // Focused on another node → move
        await obsNavigate('move', nodeId);
      } else {
        // Global scope → focus
        await obsNavigate('focus', nodeId);
      }
      return;
    }
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

  const obsNavigate = async (action, nodeId = null) => {
    if (!session?.session_id) return;
    try {
      await api.navigateObservation(session.session_id, action, nodeId);
      // Refresh observation snapshot
      const data = await api.getObservation(session.session_id);
      setSnapshot(data);
      setObsInfo(data.observation || null);
    } catch (e) {
      setError(e.message);
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

        {!session && (
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
            <button
              className="btn btn-primary"
              onClick={handleLoad}
              disabled={backendOk === false}
            >
              Load
            </button>
            {backendOk === false && (
              <span className="toolbar-warn">Backend offline</span>
            )}
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

        {session && (
          <button
            className={`btn ${observing ? 'btn-active' : ''}`}
            onClick={() => setObserving((o) => !o)}
            title="Toggle observation mode"
          >
            {observing ? '🔍 Observing' : '👁 Observe'}
          </button>
        )}
      </div>

      {/* ── Error ────────────────────────── */}
      {error && (
        <div className="error-bar" onClick={() => setError(null)}>
          {error}
          <span className="error-dismiss">✕</span>
        </div>
      )}

      {/* ── Observation controls ────────── */}
      {observing && obsInfo && (
        <div className="obs-panel">
          <div className="obs-header">
            <span className="obs-scope">{obsInfo.scope === 'g' ? 'Global' : `Node: ${obsInfo.focused_node}`}</span>
            <span className="obs-depth">{obsInfo.depth}</span>
          </div>
          <div className="obs-controls">
            <button className="btn btn-sm" onClick={() => obsNavigate('retreat')} disabled={obsInfo.depth_index <= 0}>▲ Retreat</button>
            <button className="btn btn-sm" onClick={() => obsNavigate('deepen')} disabled={obsInfo.depth_index >= 4}>▼ Deepen</button>
            {obsInfo.focused_node && (
              <button className="btn btn-sm" onClick={() => obsNavigate('defocus')}>⊕ Defocus</button>
            )}
          </div>
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

// ── Built-in scenarios ──────────────────────────────────

const SCENARIOS = {
  // ── Structural primitives ─────────────────
  greedy_trap: {
    label: 'Greedy Trap',
    desc: 'A↔C loop traps greedy; amplitude finds forward path',
    start: 'S',
    goal: 'GOAL',
    spec: {
      nodes: ['S', 'A', 'B', 'C', 'D', 'GOAL'],
      edges: [
        { from: 'S', to: 'A', delta: 0.3, resistance: 0.4 },
        { from: 'A', to: 'B', delta: 0.3, resistance: 0.5 },
        { from: 'B', to: 'D', delta: 0.3, resistance: 0.5 },
        { from: 'D', to: 'GOAL', delta: 0.2, resistance: 0.3 },
        { from: 'A', to: 'C', delta: 0.2, resistance: 0.4 },
        { from: 'C', to: 'A', delta: 0.2, resistance: 0.4 },
      ],
    },
  },
  gordian: {
    label: 'Gordian Knot (interference)',
    desc: 'Decoy A: ΔΘ≈π destructive interference. Detour B: coherent.',
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
  gordian_failure: {
    label: 'Gordian Knot (failure)',
    desc: 'S→A fails. Historization learns to pick S→B→C→GOAL.',
    start: 'S',
    goal: 'GOAL',
    spec: {
      nodes: ['S', 'A', 'X', 'B', 'C', 'GOAL'],
      edges: [
        { from: 'S', to: 'A', delta: 0.2, resistance: 0.3 },
        { from: 'A', to: 'X', delta: 0.2, resistance: 0.4 },
        { from: 'X', to: 'S', delta: 0.3, resistance: 0.5 },
        { from: 'S', to: 'B', delta: 0.3, resistance: 0.5 },
        { from: 'B', to: 'C', delta: 0.3, resistance: 0.5 },
        { from: 'C', to: 'GOAL', delta: 0.2, resistance: 0.3 },
      ],
    },
  },
  nested_cycles: {
    label: 'Nested Cycles',
    desc: 'Inner S→A→B→S (fails) + outer A→C→D→A. Exit: B→GOAL.',
    start: 'S',
    goal: 'GOAL',
    spec: {
      nodes: ['S', 'A', 'B', 'C', 'D', 'GOAL'],
      edges: [
        { from: 'S', to: 'A', delta: 0.2, resistance: 0.4 },
        { from: 'A', to: 'B', delta: 0.2, resistance: 0.4 },
        { from: 'B', to: 'S', delta: 0.15, resistance: 0.3 },
        { from: 'A', to: 'C', delta: 0.5, resistance: 0.7 },
        { from: 'C', to: 'D', delta: 0.3, resistance: 0.5 },
        { from: 'D', to: 'A', delta: 0.4, resistance: 0.6 },
        { from: 'B', to: 'GOAL', delta: 0.15, resistance: 0.4 },
      ],
    },
  },
  bottleneck: {
    label: 'Bottleneck Funnel',
    desc: 'S→X dead-end fails. Only path: S→A→B(chokepoint)→C→GOAL.',
    start: 'S',
    goal: 'GOAL',
    spec: {
      nodes: ['S', 'X', 'A', 'B', 'C', 'GOAL'],
      edges: [
        { from: 'S', to: 'X', delta: 0.2, resistance: 0.3 },
        { from: 'S', to: 'A', delta: 0.3, resistance: 0.4 },
        { from: 'A', to: 'B', delta: 0.3, resistance: 0.8 },
        { from: 'B', to: 'C', delta: 0.2, resistance: 0.3 },
        { from: 'C', to: 'GOAL', delta: 0.1, resistance: 0.2 },
      ],
    },
  },
  wide_dag: {
    label: 'Wide DAG (5 paths)',
    desc: '5 parallel S→Ai→M→GOAL. Pure DAG, no cycles.',
    start: 'S',
    goal: 'GOAL',
    spec: {
      nodes: ['S', 'A1', 'A2', 'A3', 'A4', 'A5', 'M', 'GOAL'],
      edges: [
        { from: 'S', to: 'A1', delta: 0.25, resistance: 0.4 },
        { from: 'S', to: 'A2', delta: 0.30, resistance: 0.5 },
        { from: 'S', to: 'A3', delta: 0.35, resistance: 0.6 },
        { from: 'S', to: 'A4', delta: 0.40, resistance: 0.7 },
        { from: 'S', to: 'A5', delta: 0.45, resistance: 0.8 },
        { from: 'A1', to: 'M', delta: 0.25, resistance: 0.4 },
        { from: 'A2', to: 'M', delta: 0.30, resistance: 0.5 },
        { from: 'A3', to: 'M', delta: 0.35, resistance: 0.6 },
        { from: 'A4', to: 'M', delta: 0.40, resistance: 0.7 },
        { from: 'A5', to: 'M', delta: 0.45, resistance: 0.8 },
        { from: 'M', to: 'GOAL', delta: 0.1, resistance: 0.2 },
      ],
    },
  },
  linear_chain: {
    label: 'Linear Chain (8 nodes)',
    desc: 'No branching, pure forward. Baseline.',
    start: 'S',
    goal: 'GOAL',
    spec: {
      nodes: ['S', 'A', 'B', 'C', 'D', 'E', 'F', 'GOAL'],
      edges: [
        { from: 'S', to: 'A', delta: 0.3, resistance: 0.5 },
        { from: 'A', to: 'B', delta: 0.3, resistance: 0.5 },
        { from: 'B', to: 'C', delta: 0.3, resistance: 0.5 },
        { from: 'C', to: 'D', delta: 0.3, resistance: 0.5 },
        { from: 'D', to: 'E', delta: 0.3, resistance: 0.5 },
        { from: 'E', to: 'F', delta: 0.3, resistance: 0.5 },
        { from: 'F', to: 'GOAL', delta: 0.3, resistance: 0.5 },
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
    desc: '3-node loop with leakage. Tests coherent cycling.',
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
  // ── Real-world domains ────────────────────
  invoice: {
    label: 'Invoice Process (10 nodes)',
    desc: 'Business process: RECEIVED→APPROVED. Dead-ends, escalation, recovery.',
    start: 'RECEIVED',
    goal: 'APPROVED',
    spec: {
      nodes: ['RECEIVED', 'PDF_LOADED', 'DATA_EXTRACTED', 'CUSTOMER_FOUND',
              'AMOUNT_OK', 'CONTRACT_MATCH', 'POLICY_OK', 'APPROVED',
              'REJECTED', 'HUMAN_REVIEW'],
      edges: [
        { from: 'RECEIVED', to: 'PDF_LOADED', delta: 0.2, resistance: 0.3 },
        { from: 'PDF_LOADED', to: 'DATA_EXTRACTED', delta: 0.4, resistance: 0.8 },
        { from: 'DATA_EXTRACTED', to: 'CUSTOMER_FOUND', delta: 0.5, resistance: 1.2 },
        { from: 'CUSTOMER_FOUND', to: 'AMOUNT_OK', delta: 0.2, resistance: 0.4 },
        { from: 'AMOUNT_OK', to: 'CONTRACT_MATCH', delta: 0.5, resistance: 1.0 },
        { from: 'CONTRACT_MATCH', to: 'POLICY_OK', delta: 0.3, resistance: 0.7 },
        { from: 'POLICY_OK', to: 'APPROVED', delta: 0.1, resistance: 0.2 },
        { from: 'PDF_LOADED', to: 'REJECTED', delta: 0.8, resistance: 0.5 },
        { from: 'DATA_EXTRACTED', to: 'HUMAN_REVIEW', delta: 0.6, resistance: 1.5 },
        { from: 'CUSTOMER_FOUND', to: 'HUMAN_REVIEW', delta: 0.5, resistance: 1.8 },
        { from: 'AMOUNT_OK', to: 'REJECTED', delta: 0.7, resistance: 1.0 },
        { from: 'CONTRACT_MATCH', to: 'HUMAN_REVIEW', delta: 0.4, resistance: 2.0 },
        { from: 'POLICY_OK', to: 'REJECTED', delta: 0.6, resistance: 0.8 },
        { from: 'HUMAN_REVIEW', to: 'CUSTOMER_FOUND', delta: 0.3, resistance: 2.5 },
        { from: 'HUMAN_REVIEW', to: 'DATA_EXTRACTED', delta: 0.4, resistance: 3.0 },
        { from: 'HUMAN_REVIEW', to: 'REJECTED', delta: 0.3, resistance: 3.0 },
      ],
    },
  },
  ibuprofen: {
    label: 'Ibuprofen (medical)',
    desc: 'Medication landscape: dose escalation trap, side effects, amplitude finds safer route.',
    start: 'KOPFSCHMERZ',
    goal: 'GESUND',
    spec: {
      nodes: ['KOPFSCHMERZ', 'IBU_400', 'PARACETAMOL', 'BESSERUNG', 'GESUND',
              'KEINE_WIRKUNG', 'IBU_800', 'MAGEN_REIZUNG', 'NIERE_STRESS',
              'HERZ_RISIKO', 'MAGENULKUS', 'ABSETZEN', 'LEBER_STRESS'],
      edges: [
        { from: 'KOPFSCHMERZ', to: 'IBU_400', delta: 0.80, resistance: 0.15 },
        { from: 'KOPFSCHMERZ', to: 'PARACETAMOL', delta: 0.70, resistance: 0.20 },
        { from: 'IBU_400', to: 'BESSERUNG', delta: 0.90, resistance: 0.20 },
        { from: 'PARACETAMOL', to: 'BESSERUNG', delta: 0.80, resistance: 0.15 },
        { from: 'BESSERUNG', to: 'GESUND', delta: 0.60, resistance: 0.10 },
        { from: 'IBU_400', to: 'KEINE_WIRKUNG', delta: 0.30, resistance: 0.50 },
        { from: 'KEINE_WIRKUNG', to: 'IBU_800', delta: 0.70, resistance: 0.25 },
        { from: 'IBU_800', to: 'BESSERUNG', delta: 0.90, resistance: 0.15 },
        { from: 'IBU_400', to: 'MAGEN_REIZUNG', delta: 0.50, resistance: 0.50 },
        { from: 'IBU_800', to: 'MAGEN_REIZUNG', delta: 0.60, resistance: 0.35 },
        { from: 'IBU_800', to: 'NIERE_STRESS', delta: 0.40, resistance: 0.60 },
        { from: 'IBU_800', to: 'HERZ_RISIKO', delta: 0.30, resistance: 0.70 },
        { from: 'MAGEN_REIZUNG', to: 'MAGENULKUS', delta: 0.70, resistance: 0.45 },
        { from: 'MAGEN_REIZUNG', to: 'ABSETZEN', delta: 0.50, resistance: 0.30 },
        { from: 'PARACETAMOL', to: 'LEBER_STRESS', delta: 0.40, resistance: 0.65 },
        { from: 'ABSETZEN', to: 'KOPFSCHMERZ', delta: 0.60, resistance: 0.30 },
      ],
    },
  },
  ezb: {
    label: 'EZB Monetary Policy (11 nodes)',
    desc: 'Macro-economy cycles: inflation→rate hike→recession→rate cut→growth. Stagflation trap.',
    start: 'INFLATION_HOCH',
    goal: 'PREISSTABILITAET',
    spec: {
      nodes: ['INFLATION_HOCH', 'ZINS_ERHOEHUNG', 'INFLATION_SINKT',
              'PREISSTABILITAET', 'REZESSION', 'ARBEITSLOSIGKEIT',
              'ZINS_SENKUNG', 'KREDIT_EXPANSION', 'WACHSTUM',
              'STAGFLATION', 'STRUKTURREFORM'],
      edges: [
        { from: 'INFLATION_HOCH', to: 'ZINS_ERHOEHUNG', delta: 0.80, resistance: 0.20 },
        { from: 'ZINS_ERHOEHUNG', to: 'INFLATION_SINKT', delta: 0.70, resistance: 0.25 },
        { from: 'INFLATION_SINKT', to: 'PREISSTABILITAET', delta: 0.60, resistance: 0.20 },
        { from: 'ZINS_ERHOEHUNG', to: 'REZESSION', delta: 0.50, resistance: 0.55 },
        { from: 'REZESSION', to: 'ARBEITSLOSIGKEIT', delta: 0.70, resistance: 0.30 },
        { from: 'ARBEITSLOSIGKEIT', to: 'ZINS_SENKUNG', delta: 0.80, resistance: 0.20 },
        { from: 'REZESSION', to: 'ZINS_SENKUNG', delta: 0.70, resistance: 0.25 },
        { from: 'ZINS_SENKUNG', to: 'KREDIT_EXPANSION', delta: 0.60, resistance: 0.35 },
        { from: 'KREDIT_EXPANSION', to: 'WACHSTUM', delta: 0.50, resistance: 0.30 },
        { from: 'WACHSTUM', to: 'INFLATION_HOCH', delta: 0.40, resistance: 0.55 },
        { from: 'WACHSTUM', to: 'PREISSTABILITAET', delta: 0.30, resistance: 0.20 },
        { from: 'PREISSTABILITAET', to: 'WACHSTUM', delta: 0.40, resistance: 0.25 },
        { from: 'STAGFLATION', to: 'ZINS_ERHOEHUNG', delta: 0.60, resistance: 0.75 },
        { from: 'STAGFLATION', to: 'ZINS_SENKUNG', delta: 0.50, resistance: 0.80 },
        { from: 'STAGFLATION', to: 'STRUKTURREFORM', delta: 0.70, resistance: 0.70 },
        { from: 'STRUKTURREFORM', to: 'WACHSTUM', delta: 0.60, resistance: 0.55 },
      ],
    },
  },
  diamond: {
    label: 'Diamond (simple)',
    desc: 'S→A (easy start, hard finish) vs S→B (hard start, easy finish).',
    start: 'S',
    goal: 'G',
    spec: {
      nodes: ['S', 'A', 'B', 'G'],
      edges: [
        { from: 'S', to: 'A', delta: 0.3, resistance: 0.4 },
        { from: 'A', to: 'G', delta: 0.5, resistance: 2.0 },
        { from: 'S', to: 'B', delta: 0.5, resistance: 0.6 },
        { from: 'B', to: 'G', delta: 0.2, resistance: 0.3 },
      ],
    },
  },
};
