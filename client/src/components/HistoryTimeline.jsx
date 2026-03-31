/**
 * HistoryTimeline — scrollable step history.
 */
export default function HistoryTimeline({ history }) {
  if (!history.length) {
    return (
      <div className="history-panel">
        <h3>History</h3>
        <p className="empty">No steps yet.</p>
      </div>
    );
  }

  return (
    <div className="history-panel">
      <h3>History ({history.length} steps)</h3>
      <div className="history-list">
        {history.map((e, i) => (
          <div
            key={i}
            className={`history-item ${e.outcome === 'success' ? 'success' : 'failure'} ${e.escalated ? 'escalated' : ''}`}
          >
            <span className="history-tau">τ{e.tau}</span>
            <span className="history-edge">{e.source} → {e.target}</span>
            <span className={`history-outcome ${e.outcome}`}>{e.outcome}</span>
            {e.escalated && (
              <span className="history-esc" title={e.escalation_type}>⚡</span>
            )}
            {e.overload_index != null && (
              <span className="history-oi" title="Overload Index">OI:{e.overload_index.toFixed(1)}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
