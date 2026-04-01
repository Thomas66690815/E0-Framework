import { useState, useEffect } from 'react';
import * as api from '../api';

/**
 * ControlPanel — input mode, start/pause/step, speed, canon selector.
 */
export default function ControlPanel({
  session,
  running,
  snapshot,
  onCreateSession,
  onStart,
  onStep,
  onPause,
  onResume,
  onAutoRun,
  onStopAutoRun,
  onSetSpeed,
}) {
  const [mode, setMode] = useState('json');
  const [specText, setSpecText] = useState(DEFAULT_SPEC);
  const [canonName, setCanonName] = useState('');
  const [canons, setCanons] = useState([]);
  const [startNode, setStartNode] = useState('');
  const [goalNode, setGoalNode] = useState('');
  const [maxCycles, setMaxCycles] = useState(50);
  const [speed, setSpeed] = useState(200);

  useEffect(() => {
    api.listCanons().then(setCanons).catch(() => {});
  }, []);

  // Auto-populate start node from landscape states
  const landscapeStates = snapshot?.landscape?.states || [];
  useEffect(() => {
    if (landscapeStates.length > 0 && !startNode) {
      setStartNode(landscapeStates[0]);
    }
  }, [landscapeStates.length]);

  const handleCreate = async () => {
    const opts = {};
    if (mode === 'json') {
      try {
        opts.spec = JSON.parse(specText);
      } catch {
        alert('Invalid JSON spec');
        return;
      }
    } else if (mode === 'canon') {
      opts.canon_name = canonName;
    } else if (mode === 'text') {
      opts.text = specText;
    }
    onCreateSession(mode, opts);
  };

  const handleStart = () => {
    if (!startNode) { alert('Start node required'); return; }
    onStart(startNode, goalNode || null, maxCycles);
  };

  const handleSpeedChange = (e) => {
    const v = Number(e.target.value);
    setSpeed(v);
    onSetSpeed(v);
  };

  const state = session?.state;
  const isCreated = state === 'created';
  const isRunning = state === 'running';
  const isPaused = state === 'paused';
  const isCompleted = state === 'completed';
  const canStep = isRunning && !running;
  const canAutoRun = isRunning && !running;
  const canPause = isRunning && running;

  return (
    <div className="control-panel">
      <h2>Control</h2>

      {/* ── Session Creation ────────────────── */}
      {!session && (
        <fieldset>
          <legend>New Session</legend>
          <div className="control-row">
            <label>Mode:</label>
            <select value={mode} onChange={(e) => setMode(e.target.value)}>
              <option value="json">JSON Spec</option>
              <option value="canon">Canon</option>
              <option value="text">Text (LLM)</option>
            </select>
          </div>

          {mode === 'json' && (
            <textarea
              className="spec-input"
              rows={8}
              value={specText}
              onChange={(e) => setSpecText(e.target.value)}
            />
          )}

          {mode === 'canon' && (
            <div className="control-row">
              <label>Canon:</label>
              <select value={canonName} onChange={(e) => setCanonName(e.target.value)}>
                <option value="">— select —</option>
                {canons.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
          )}

          {mode === 'text' && (
            <textarea
              className="spec-input"
              rows={4}
              placeholder="Describe the problem domain…"
              value={specText}
              onChange={(e) => setSpecText(e.target.value)}
            />
          )}

          <button className="btn btn-primary" onClick={handleCreate}>Create Session</button>
        </fieldset>
      )}

      {/* ── Start Configuration ─────────────── */}
      {isCreated && (
        <fieldset>
          <legend>Start Run</legend>
          <div className="control-row">
            <label>Start:</label>
            {landscapeStates.length > 0 ? (
              <select value={startNode} onChange={(e) => setStartNode(e.target.value)}>
                {landscapeStates.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            ) : (
              <input value={startNode} onChange={(e) => setStartNode(e.target.value)} placeholder="state name" />
            )}
          </div>
          <div className="control-row">
            <label>Goal:</label>
            {landscapeStates.length > 0 ? (
              <select value={goalNode} onChange={(e) => setGoalNode(e.target.value)}>
                <option value="">(none)</option>
                {landscapeStates.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            ) : (
              <input value={goalNode} onChange={(e) => setGoalNode(e.target.value)} placeholder="(optional)" />
            )}
          </div>
          <div className="control-row">
            <label>Max cycles:</label>
            <input type="number" min={1} max={10000} value={maxCycles} onChange={(e) => setMaxCycles(Number(e.target.value))} />
          </div>
          <button className="btn btn-primary" onClick={handleStart}>Start</button>
        </fieldset>
      )}

      {/* ── Run Controls ────────────────────── */}
      {(isRunning || isPaused) && (
        <fieldset>
          <legend>Run</legend>
          <div className="control-buttons">
            {canStep && <button className="btn" onClick={onStep}>Step</button>}
            {canAutoRun && <button className="btn btn-primary" onClick={() => onAutoRun(speed)}>▶ Auto</button>}
            {canPause && <button className="btn btn-warn" onClick={() => { onStopAutoRun(); onPause(); }}>⏸ Pause</button>}
            {isPaused && <button className="btn btn-primary" onClick={onResume}>▶ Resume</button>}
          </div>
          <div className="control-row">
            <label>Speed: {speed}ms</label>
            <input type="range" min={10} max={2000} step={10} value={speed} onChange={handleSpeedChange} />
          </div>
        </fieldset>
      )}

      {/* ── Completed ───────────────────────── */}
      {isCompleted && (
        <fieldset>
          <legend>Completed</legend>
          <p>Run finished after {session.history_length} steps.</p>
        </fieldset>
      )}
    </div>
  );
}

const DEFAULT_SPEC = JSON.stringify({
  nodes: ['A', 'B', 'C', 'D', 'E'],
  edges: [
    { from: 'A', to: 'B', delta: 0.5, resistance: 1.0 },
    { from: 'A', to: 'C', delta: 0.3, resistance: 1.5 },
    { from: 'B', to: 'D', delta: 0.4, resistance: 1.0 },
    { from: 'C', to: 'D', delta: 0.6, resistance: 0.8 },
    { from: 'D', to: 'E', delta: 0.5, resistance: 1.0 },
  ],
}, null, 2);
