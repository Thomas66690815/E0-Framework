import { useEffect, useRef } from 'react';
import cytoscape from 'cytoscape';

/**
 * GraphView — Cytoscape.js graph visualization.
 *
 * Nodes: color = trace_quality(q), size = trace_load(m), glow = current position.
 * Edges: thickness ∝ 1/S_eff, color = δ_H (green/red/gray).
 */
export default function GraphView({ snapshot, session, history }) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);

  // Initialize Cytoscape
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
            'font-size': '11px',
            'font-weight': 'bold',
            color: '#fff',
            'text-outline-width': 1.5,
            'text-outline-color': '#333',
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
          selector: 'node.visited',
          style: {
            'text-outline-color': '#555',
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
            opacity: 0.8,
            'font-size': '9px',
          },
        },
        {
          selector: 'edge.recent',
          style: {
            'line-style': 'solid',
            opacity: 1.0,
            width: 4,
            'line-color': '#FFD700',
            'target-arrow-color': '#FFD700',
          },
        },
      ],
      layout: { name: 'cose', animate: false, padding: 30, nodeRepulsion: 8000 },
      minZoom: 0.3,
      maxZoom: 3,
    });

    cyRef.current = cy;

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, []);

  // Update graph data when snapshot changes
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || !snapshot) return;

    const elements = buildElements(snapshot, session, history);

    cy.json({ elements });
    // Only run layout if element count changed
    cy.layout({ name: 'cose', animate: true, animationDuration: 300, padding: 30, nodeRepulsion: 8000 }).run();
  }, [snapshot]);

  // Update classes when session/history updates (position, visited)
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || !session) return;

    // Update current position
    cy.nodes().removeClass('current goal visited');
    if (session.current_position) {
      cy.getElementById(session.current_position).addClass('current');
    }
    if (session.goal) {
      cy.getElementById(session.goal).addClass('goal');
    }

    // Mark visited nodes
    const visited = new Set(history.map((e) => e.source));
    if (history.length > 0) visited.add(history[history.length - 1].target);
    visited.forEach((v) => cy.getElementById(v).addClass('visited'));

    // Highlight recent edge
    cy.edges().removeClass('recent');
    if (history.length > 0) {
      const last = history[history.length - 1];
      const edgeId = `${last.source}-${last.target}`;
      cy.getElementById(edgeId).addClass('recent');
    }
  }, [session, history]);

  return <div ref={containerRef} className="graph-view" />;
}


// ── Helpers ─────────────────────────────────────────────

function buildElements(snapshot, session, history) {
  const nodes = [];
  const edges = [];
  const landscape = snapshot?.landscape;
  if (!landscape) return { nodes, edges };

  const states = landscape.states || [];
  const edgeMap = landscape.edges || {};

  // Gather trace_load range for size mapping
  let maxLoad = 1;
  for (const edata of Object.values(edgeMap)) {
    const load = (edata.trace_load || 0);
    if (load > maxLoad) maxLoad = load;
  }

  // Per-node: accumulate trace_quality from incident edges
  const nodeQ = {};
  const nodeLoad = {};
  for (const s of states) {
    nodeQ[s] = 0;
    nodeLoad[s] = 0;
  }
  for (const edata of Object.values(edgeMap)) {
    const src = edata.source;
    const tgt = edata.target;
    const q = edata.trace_quality || 0;
    const ld = edata.trace_load || 0;
    if (nodeQ[src] !== undefined) { nodeQ[src] += q; nodeLoad[src] += ld; }
    if (nodeQ[tgt] !== undefined) { nodeQ[tgt] += q; nodeLoad[tgt] += ld; }
  }

  for (const s of states) {
    const avgQ = nodeQ[s] / Math.max(1, Object.values(edgeMap).filter((e) => e.source === s || e.target === s).length);
    const size = 25 + Math.min(nodeLoad[s] / Math.max(1, maxLoad), 1) * 35;
    nodes.push({
      data: {
        id: s,
        label: s,
        color: qualityColor(avgQ),
        size: Math.round(size),
      },
    });
  }

  for (const [key, edata] of Object.entries(edgeMap)) {
    const sEff = edata.S_eff || 1;
    const deltaH = edata.delta_H || 0;
    const thickness = Math.max(1, Math.min(6, 4 / sEff));

    edges.push({
      data: {
        id: `${edata.source}-${edata.target}`,
        source: edata.source,
        target: edata.target,
        thickness: Math.round(thickness * 10) / 10,
        color: deltaHColor(deltaH),
      },
    });
  }

  return { nodes, edges };
}

function qualityColor(q) {
  // q ∈ [-1, +1] → red → yellow → green
  const clamped = Math.max(-1, Math.min(1, q));
  if (clamped >= 0) {
    // 0 = yellow (#EAB308), 1 = green (#22C55E)
    const r = Math.round(234 - clamped * (234 - 34));
    const g = Math.round(179 + clamped * (197 - 179));
    const b = Math.round(8 + clamped * (94 - 8));
    return `rgb(${r},${g},${b})`;
  } else {
    // -1 = red (#EF4444), 0 = yellow (#EAB308)
    const t = clamped + 1; // 0..1
    const r = Math.round(239 - t * (239 - 234));
    const g = Math.round(68 + t * (179 - 68));
    const b = Math.round(68 - t * (68 - 8));
    return `rgb(${r},${g},${b})`;
  }
}

function deltaHColor(dH) {
  if (Math.abs(dH) < 0.01) return '#888';    // untouched: gray
  if (dH > 0) return '#22C55E';               // positive history: green
  return '#EF4444';                            // negative history: red
}
