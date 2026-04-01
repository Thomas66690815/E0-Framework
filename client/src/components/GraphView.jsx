import { useEffect, useRef, useState } from 'react';
import cytoscape from 'cytoscape';

/**
 * GraphView — the entire E₀ interface surface.
 *
 * The graph fills the screen. Field selector controls what dimension
 * is projected onto edge color/thickness. Click edges to inspect
 * the full numeric profile. Click nodes to interact.
 */
export default function GraphView({ snapshot, session, history, field, onNodeClick }) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);
  const [inspected, setInspected] = useState(null); // edge data or null
  const prevCountRef = useRef(0);

  // Initialize Cytoscape once
  useEffect(() => {
    if (!containerRef.current) return;

    const cy = cytoscape({
      container: containerRef.current,
      style: [
        {
          selector: 'node',
          style: {
            label: 'data(label)',
            'text-valign': 'center',
            'text-halign': 'center',
            'font-size': '12px',
            'font-weight': 'bold',
            color: '#e0e0e0',
            'text-outline-width': 2,
            'text-outline-color': '#1a1a2e',
            width: 'data(size)',
            height: 'data(size)',
            'background-color': 'data(color)',
            'border-width': 0,
          },
        },
        {
          selector: 'node.current',
          style: {
            'border-width': 4,
            'border-color': '#FFD700',
            'border-style': 'solid',
          },
        },
        {
          selector: 'node.goal',
          style: {
            'border-width': 3,
            'border-color': '#00BFFF',
            'border-style': 'dashed',
          },
        },
        {
          selector: 'node.clickable',
          style: {
            'border-width': 2,
            'border-color': '#3B82F6',
            'border-style': 'dotted',
            cursor: 'pointer',
          },
        },
        {
          selector: 'edge',
          style: {
            width: 'data(thickness)',
            'line-color': 'data(color)',
            'target-arrow-color': 'data(color)',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            opacity: 'data(opacity)',
            label: 'data(valueLabel)',
            'font-size': '10px',
            'font-family': "'Cascadia Code', 'Consolas', monospace",
            color: '#ccc',
            'text-outline-width': 2,
            'text-outline-color': '#0f0f1a',
            'text-rotation': 'autorotate',
            'text-margin-y': -8,
          },
        },
        {
          selector: 'edge.recent',
          style: {
            opacity: 1.0,
            width: 5,
            'line-color': '#FFD700',
            'target-arrow-color': '#FFD700',
          },
        },
        {
          selector: 'edge.inspected',
          style: {
            'line-color': '#3B82F6',
            'target-arrow-color': '#3B82F6',
            opacity: 1.0,
          },
        },
      ],
      layout: { name: 'cose', animate: false, padding: 50, nodeRepulsion: 10000 },
      minZoom: 0.3,
      maxZoom: 3,
    });

    // Edge click → inspect
    cy.on('tap', 'edge', (evt) => {
      const data = evt.target.data();
      setInspected(data.profile || null);
      cy.edges().removeClass('inspected');
      evt.target.addClass('inspected');
    });

    // Node click → handler
    cy.on('tap', 'node', (evt) => {
      onNodeClick?.(evt.target.id());
    });

    // Background click → dismiss inspection
    cy.on('tap', (evt) => {
      if (evt.target === cy) {
        setInspected(null);
        cy.edges().removeClass('inspected');
      }
    });

    cyRef.current = cy;
    return () => { cy.destroy(); cyRef.current = null; };
  }, []);

  // Update onNodeClick ref without recreating cy
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.removeListener('tap', 'node');
    cy.on('tap', 'node', (evt) => onNodeClick?.(evt.target.id()));
  }, [onNodeClick]);

  // Update graph when snapshot or field changes
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || !snapshot?.landscape) return;

    const elements = buildElements(snapshot, field);
    const prevCount = prevCountRef.current;
    const newCount = (elements.nodes?.length || 0) + (elements.edges?.length || 0);

    cy.json({ elements });

    // Only re-layout when element count changes (new landscape)
    if (newCount !== prevCount) {
      cy.layout({ name: 'cose', animate: true, animationDuration: 400, padding: 50, nodeRepulsion: 10000 }).run();
      prevCountRef.current = newCount;
    }
  }, [snapshot, field]);

  // Update classes for position/visited/recent
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;

    cy.nodes().removeClass('current goal clickable');
    cy.edges().removeClass('recent');

    if (session?.state === 'created') {
      cy.nodes().addClass('clickable');
    }
    if (session?.current_position) {
      cy.getElementById(session.current_position).addClass('current');
    }
    if (session?.goal) {
      cy.getElementById(session.goal).addClass('goal');
    }
    if (history.length > 0) {
      const last = history[history.length - 1];
      cy.getElementById(`${last.source}-${last.target}`).addClass('recent');
    }
  }, [session, history]);

  return (
    <div className="graph-container">
      <div ref={containerRef} className="graph-canvas" />

      {/* Edge inspection panel */}
      {inspected && (
        <div className="edge-profile">
          <div className="profile-header">
            {inspected.source} → {inspected.target}
            <button className="profile-close" onClick={() => { setInspected(null); cyRef.current?.edges().removeClass('inspected'); }}>✕</button>
          </div>
          <table className="profile-table">
            <tbody>
              <tr><td>U</td><td>{fmt(inspected.U)}</td><td>F</td><td>{fmt(inspected.F)}</td></tr>
              <tr><td>q</td><td>{fmt(inspected.trace_quality)}</td><td>m</td><td>{fmt(inspected.trace_load)}</td></tr>
              <tr><td>S_eff</td><td>{fmt(inspected.S_eff)}</td><td>R_eff</td><td>{fmt(inspected.R_eff)}</td></tr>
              <tr><td>δ_H</td><td className={inspected.delta_H > 0 ? 'positive' : inspected.delta_H < 0 ? 'negative' : ''}>{fmt(inspected.delta_H, true)}</td>
                  <td>coh</td><td>{fmt(inspected.coherence)}</td></tr>
              <tr><td>δ</td><td>{fmt(inspected.delta)}</td><td>R₀</td><td>{fmt(inspected.R0)}</td></tr>
            </tbody>
          </table>
        </div>
      )}

      {/* Color legend */}
      {snapshot?.landscape && (
        <div className="color-legend">
          <div className="legend-title">{FIELD_META[field]?.label || field}</div>
          <div className="legend-bar" style={{ background: FIELD_META[field]?.gradient }} />
          <div className="legend-labels">
            <span>{FIELD_META[field]?.min}</span>
            <span>{FIELD_META[field]?.max}</span>
          </div>
          <div className="legend-desc">{FIELD_META[field]?.desc}</div>
        </div>
      )}

      {/* Empty state */}
      {!snapshot && (
        <div className="graph-empty">
          Load a landscape to begin
        </div>
      )}
    </div>
  );
}


// ── Field metadata (for legend + edge labels) ──────────

const FIELD_META = {
  trace_quality: {
    label: 'trace_quality (q)',
    min: '-1', max: '+1',
    desc: 'Learned quality: red = failure, green = success',
    gradient: 'linear-gradient(to right, rgb(220,60,60), rgb(140,120,120), rgb(40,200,70))',
    fmt: (v) => v.toFixed(2),
  },
  trace_load: {
    label: 'trace_load (m)',
    min: '0', max: 'max',
    desc: 'Traversal count — thickness shows load',
    gradient: 'linear-gradient(to right, rgb(30,60,120), rgb(70,220,240))',
    fmt: (v) => v.toFixed(1),
  },
  S_eff: {
    label: 'S_eff (effective tension)',
    min: '0', max: '3+',
    desc: 'Drive — thick = low resistance path',
    gradient: 'linear-gradient(to right, rgb(30,60,120), rgb(70,220,240))',
    fmt: (v) => v.toFixed(2),
  },
  R_eff: {
    label: 'R_eff (effective resistance)',
    min: '0', max: '3+',
    desc: 'How hard to traverse this edge',
    gradient: 'linear-gradient(to right, rgb(30,60,120), rgb(70,220,240))',
    fmt: (v) => v.toFixed(2),
  },
  delta_H: {
    label: 'δ_H (historization change)',
    min: '-0.5', max: '+0.5',
    desc: 'Red = decaying, green = growing inscription',
    gradient: 'linear-gradient(to right, rgb(220,60,60), rgb(140,120,120), rgb(40,200,70))',
    fmt: (v) => (v > 0 ? '+' : '') + v.toFixed(3),
  },
  coherence: {
    label: 'coherence (U/(U+F))',
    min: '0', max: '1',
    desc: 'Ratio of success to total traces',
    gradient: 'linear-gradient(to right, rgb(30,60,120), rgb(70,220,240))',
    fmt: (v) => v.toFixed(2),
  },
  inertia: {
    label: 'inertia_factor (ι)',
    min: '0', max: '1',
    desc: 'High = stale edge, low = actively used',
    gradient: 'linear-gradient(to right, rgb(30,60,120), rgb(70,220,240))',
    fmt: (v) => v.toFixed(3),
  },
};


// ── Field mapping ───────────────────────────────────────

const FIELD_CONFIG = {
  trace_quality: {
    edgeColor: (e) => divergentColor(e.trace_quality, -1, 1),
    edgeThickness: () => 2.5,
    edgeOpacity: () => 0.85,
    nodeColor: (avgVal) => divergentColor(avgVal, -1, 1),
    nodeSize: () => 35,
  },
  trace_load: {
    edgeColor: () => '#5588cc',
    edgeThickness: (e, max) => 1 + (e.trace_load / Math.max(1, max)) * 6,
    edgeOpacity: () => 0.8,
    nodeColor: () => '#4477aa',
    nodeSize: (avgVal, max) => 25 + (avgVal / Math.max(1, max)) * 35,
  },
  S_eff: {
    edgeColor: (e) => sequentialColor(e.S_eff, 0, 3),
    edgeThickness: (e) => Math.max(1, Math.min(6, 4 / Math.max(0.1, e.S_eff))),
    edgeOpacity: () => 0.85,
    nodeColor: () => '#5577aa',
    nodeSize: () => 35,
  },
  R_eff: {
    edgeColor: (e) => sequentialColor(e.R_eff, 0, 3),
    edgeThickness: (e) => Math.max(1, Math.min(6, e.R_eff * 2)),
    edgeOpacity: () => 0.85,
    nodeColor: () => '#5577aa',
    nodeSize: () => 35,
  },
  delta_H: {
    edgeColor: (e) => divergentColor(e.delta_H, -0.5, 0.5),
    edgeThickness: (e) => 1 + Math.abs(e.delta_H) * 8,
    edgeOpacity: (e) => 0.4 + Math.min(Math.abs(e.delta_H) * 3, 0.6),
    nodeColor: () => '#5577aa',
    nodeSize: () => 35,
  },
  coherence: {
    edgeColor: (e) => sequentialColor(e.coherence, 0, 1),
    edgeThickness: () => 2.5,
    edgeOpacity: (e) => 0.3 + (e.coherence || 0) * 0.7,
    nodeColor: () => '#5577aa',
    nodeSize: () => 35,
  },
  inertia: {
    edgeColor: (e) => sequentialColor(e.inertia || 0, 0, 1),
    edgeThickness: () => 2.5,
    edgeOpacity: (e) => 1.0 - (e.inertia || 0) * 0.6,
    nodeColor: () => '#5577aa',
    nodeSize: () => 35,
  },
};


// ── Build elements ──────────────────────────────────────

function buildElements(snapshot, field) {
  const nodes = [];
  const edges = [];
  const landscape = snapshot?.landscape;
  if (!landscape) return { nodes, edges };

  const stateList = landscape.states || [];
  const edgeMap = landscape.edges || {};
  const config = FIELD_CONFIG[field] || FIELD_CONFIG.trace_quality;

  // Compute max for normalization
  let maxVal = 1;
  for (const e of Object.values(edgeMap)) {
    const v = e[field] || 0;
    if (Math.abs(v) > maxVal) maxVal = Math.abs(v);
  }

  // Per-node: average the chosen field from incident edges
  const nodeAcc = {};
  const nodeCount = {};
  for (const s of stateList) { nodeAcc[s] = 0; nodeCount[s] = 0; }
  for (const e of Object.values(edgeMap)) {
    const v = e[field] || 0;
    if (nodeAcc[e.source] !== undefined) { nodeAcc[e.source] += v; nodeCount[e.source]++; }
    if (nodeAcc[e.target] !== undefined) { nodeAcc[e.target] += v; nodeCount[e.target]++; }
  }

  for (const s of stateList) {
    const avg = nodeCount[s] > 0 ? nodeAcc[s] / nodeCount[s] : 0;
    nodes.push({
      data: {
        id: s,
        label: s,
        color: config.nodeColor(avg, maxVal),
        size: Math.round(config.nodeSize(avg, maxVal)),
      },
    });
  }

  for (const [, e] of Object.entries(edgeMap)) {
    edges.push({
      data: {
        id: `${e.source}-${e.target}`,
        source: e.source,
        target: e.target,
        thickness: Math.round(config.edgeThickness(e, maxVal) * 10) / 10,
        color: config.edgeColor(e, maxVal),
        opacity: config.edgeOpacity(e),
        valueLabel: (FIELD_META[field]?.fmt || ((v) => v.toFixed(2)))(e[field] || 0),
        profile: e,  // full numeric data for inspection
      },
    });
  }

  return { nodes, edges };
}


// ── Color scales ────────────────────────────────────────

function divergentColor(value, min, max) {
  // min..0..max → red → gray → green
  const range = max - min;
  const t = range > 0 ? (value - min) / range : 0.5;
  const clamped = Math.max(0, Math.min(1, t));

  if (clamped < 0.5) {
    // red to gray
    const s = clamped * 2;
    const r = Math.round(220 - s * 80);
    const g = Math.round(60 + s * 60);
    const b = Math.round(60 + s * 60);
    return `rgb(${r},${g},${b})`;
  } else {
    // gray to green
    const s = (clamped - 0.5) * 2;
    const r = Math.round(140 - s * 100);
    const g = Math.round(120 + s * 80);
    const b = Math.round(120 - s * 50);
    return `rgb(${r},${g},${b})`;
  }
}

function sequentialColor(value, min, max) {
  // min..max → dark blue → bright cyan
  const t = max > min ? Math.max(0, Math.min(1, (value - min) / (max - min))) : 0;
  const r = Math.round(30 + t * 40);
  const g = Math.round(60 + t * 160);
  const b = Math.round(120 + t * 120);
  return `rgb(${r},${g},${b})`;
}

function fmt(v, sign = false) {
  if (v === undefined || v === null) return '—';
  const s = typeof v === 'number' ? v.toFixed(3) : String(v);
  return sign && v > 0 ? `+${s}` : s;
}
