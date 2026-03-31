/**
 * Header — session info, mode indicator, tau counter.
 */
export default function Header({ session }) {
  if (!session) {
    return (
      <header className="header">
        <h1>E₀ Framework</h1>
        <span className="header-sub">No active session</span>
      </header>
    );
  }

  const stateClass = `state-${session.state}`;

  return (
    <header className="header">
      <h1>E₀ Framework</h1>
      <div className="header-info">
        <span className="header-session" title={session.session_id}>
          Session: {session.session_id.slice(0, 8)}…
        </span>
        <span className={`header-state ${stateClass}`}>
          {session.state.toUpperCase()}
        </span>
        <span className="header-mode">Mode: {session.mode}</span>
        <span className="header-tau">τ = {session.history_length}</span>
        {session.current_position && (
          <span className="header-pos">@ {session.current_position}</span>
        )}
        {session.goal && (
          <span className="header-goal">→ {session.goal}</span>
        )}
      </div>
    </header>
  );
}
