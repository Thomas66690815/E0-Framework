/**
 * PeerDialog — shown when E₀ needs human input (Zentrale mode).
 *
 * Displays candidates with edge info. Human clicks to choose.
 */
export default function PeerDialog({ peerRequest, onRespond }) {
  if (!peerRequest) return null;

  const { current, neighbors, edge_info, overload_index } = peerRequest;

  return (
    <div className="peer-dialog">
      <h3>🧭 Peer Decision Required</h3>
      <p className="peer-context">
        E₀ is at <strong>{current}</strong> with overload index{' '}
        <strong>{overload_index?.toFixed(2) ?? '?'}</strong>.
        Choose the next target:
      </p>
      <div className="peer-candidates">
        {neighbors.map((n) => {
          const info = edge_info?.[n];
          return (
            <button
              key={n}
              className="peer-candidate"
              onClick={() => onRespond(n)}
              title={info ? `S_eff=${info.S_eff?.toFixed(3)}, q=${info.trace_quality?.toFixed(2)}, m=${info.trace_load?.toFixed(1)}` : ''}
            >
              <span className="candidate-name">{n}</span>
              {info && (
                <span className="candidate-info">
                  S<sub>eff</sub>={info.S_eff?.toFixed(3)}
                  {' · '}q={info.trace_quality?.toFixed(2)}
                  {' · '}m={info.trace_load?.toFixed(1)}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
