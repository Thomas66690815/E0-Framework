import { useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

/**
 * MetricsPanel — success rate, escalation count, learning curves.
 */
export default function MetricsPanel({ history }) {
  const metrics = useMemo(() => computeMetrics(history), [history]);

  if (!history.length) {
    return (
      <div className="metrics-panel">
        <h3>Metrics</h3>
        <p className="empty">Waiting for data…</p>
      </div>
    );
  }

  return (
    <div className="metrics-panel">
      <h3>Metrics</h3>

      <div className="metrics-summary">
        <div className="metric">
          <span className="metric-value">{metrics.successRate}%</span>
          <span className="metric-label">Success Rate</span>
        </div>
        <div className="metric">
          <span className="metric-value">{metrics.escalations}</span>
          <span className="metric-label">Escalations</span>
        </div>
        <div className="metric">
          <span className="metric-value">{metrics.uniqueEdges}</span>
          <span className="metric-label">Unique Edges</span>
        </div>
      </div>

      {/* Learning curve: cumulative success rate over τ */}
      {metrics.chartData.length > 1 && (
        <div className="metrics-chart">
          <h4>Success Rate (cumulative)</h4>
          <ResponsiveContainer width="100%" height={120}>
            <LineChart data={metrics.chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#444" />
              <XAxis dataKey="tau" tick={{ fontSize: 10, fill: '#aaa' }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#aaa' }} />
              <Tooltip
                contentStyle={{ background: '#1e1e2e', border: '1px solid #444', fontSize: 11 }}
              />
              <Line type="monotone" dataKey="rate" stroke="#22C55E" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* S_eff over τ */}
      {metrics.chartData.length > 1 && (
        <div className="metrics-chart">
          <h4>Effective Tension (S<sub>eff</sub>)</h4>
          <ResponsiveContainer width="100%" height={120}>
            <LineChart data={metrics.chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#444" />
              <XAxis dataKey="tau" tick={{ fontSize: 10, fill: '#aaa' }} />
              <YAxis tick={{ fontSize: 10, fill: '#aaa' }} />
              <Tooltip
                contentStyle={{ background: '#1e1e2e', border: '1px solid #444', fontSize: 11 }}
              />
              <Line type="monotone" dataKey="sEff" stroke="#3B82F6" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}


function computeMetrics(history) {
  let successes = 0;
  let escalations = 0;
  const seenEdges = new Set();
  const chartData = [];

  for (let i = 0; i < history.length; i++) {
    const e = history[i];
    if (e.outcome === 'success') successes++;
    if (e.escalated) escalations++;
    seenEdges.add(`${e.source}→${e.target}`);

    chartData.push({
      tau: e.tau,
      rate: Math.round((successes / (i + 1)) * 100),
      sEff: e.s_eff,
    });
  }

  return {
    successRate: history.length ? Math.round((successes / history.length) * 100) : 0,
    escalations,
    uniqueEdges: seenEdges.size,
    chartData,
  };
}
