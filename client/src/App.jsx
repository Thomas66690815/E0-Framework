import { useState, useEffect, useCallback } from 'react';
import Header from './components/Header';
import ControlPanel from './components/ControlPanel';
import GraphView from './components/GraphView';
import HistoryTimeline from './components/HistoryTimeline';
import PeerDialog from './components/PeerDialog';
import MetricsPanel from './components/MetricsPanel';
import { useSession } from './hooks/useSession';
import { useWebSocket } from './hooks/useWebSocket';
import * as api from './api';
import './styles/app.css';

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
    pause,
    resume,
    autoRun,
    stopAutoRun,
    setSpeed,
    refreshSession,
    handleWsEvent,
    clearPeerRequest,
    setError,
  } = useSession();

  const [snapshot, setSnapshot] = useState(null);

  // WebSocket connection
  const ws = useWebSocket(session?.session_id, handleWsEvent);

  // Fetch snapshot after session changes or after each step
  useEffect(() => {
    if (!session?.session_id) { setSnapshot(null); return; }
    api.getSnapshot(session.session_id)
      .then(setSnapshot)
      .catch(() => {});
  }, [session?.session_id, history.length]);

  // Handle peer response
  const handlePeerResponse = useCallback((target) => {
    ws.sendPeerResponse(target);
    clearPeerRequest();
    if (session) refreshSession(session.session_id);
  }, [ws, clearPeerRequest, session, refreshSession]);

  return (
    <div className="app">
      <Header session={session} />

      {error && (
        <div className="error-bar" onClick={() => setError(null)}>
          {error}
          <span className="error-dismiss">✕</span>
        </div>
      )}

      <div className="main-layout">
        <aside className="sidebar">
          <ControlPanel
            session={session}
            running={running}
            onCreateSession={create}
            onStart={start}
            onStep={step}
            onPause={pause}
            onResume={resume}
            onAutoRun={autoRun}
            onStopAutoRun={stopAutoRun}
            onSetSpeed={setSpeed}
          />
        </aside>

        <main className="center">
          <GraphView
            snapshot={snapshot}
            session={session}
            history={history}
          />
        </main>

        <aside className="right-sidebar">
          <PeerDialog
            peerRequest={peerRequest}
            onRespond={handlePeerResponse}
          />
          <HistoryTimeline history={history} />
          <MetricsPanel history={history} />
        </aside>
      </div>
    </div>
  );
}
