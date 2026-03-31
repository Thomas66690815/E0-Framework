import { useState, useCallback, useRef } from 'react';
import * as api from '../api';

/**
 * Hook: manages E₀ session lifecycle state.
 *
 * Provides: session info, history, events, peer request state,
 * and action callbacks (create, start, step, pause, resume, autoRun).
 */
export function useSession() {
  const [session, setSession] = useState(null);       // SessionInfo
  const [history, setHistory] = useState([]);          // StepEvent[]
  const [peerRequest, setPeerRequest] = useState(null);// peer_request data or null
  const [error, setError] = useState(null);
  const [running, setRunning] = useState(false);       // autoRun active
  const autoRunRef = useRef(false);
  const speedRef = useRef(200);                        // ms between steps

  const refreshSession = useCallback(async (id) => {
    try {
      const info = await api.getSession(id);
      setSession(info);
      return info;
    } catch (e) {
      setError(e.message);
      return null;
    }
  }, []);

  const create = useCallback(async (mode, opts) => {
    try {
      setError(null);
      setHistory([]);
      setPeerRequest(null);
      const res = await api.createSession(mode, opts);
      await refreshSession(res.session_id);
      return res.session_id;
    } catch (e) {
      setError(e.message);
      return null;
    }
  }, [refreshSession]);

  const start = useCallback(async (startNode, goal, maxCycles) => {
    if (!session) return;
    try {
      setError(null);
      const info = await api.startSession(session.session_id, startNode, goal, maxCycles);
      setSession(info);
    } catch (e) {
      setError(e.message);
    }
  }, [session]);

  const step = useCallback(async () => {
    if (!session) return null;
    try {
      setError(null);
      const event = await api.stepSession(session.session_id);
      if (event) {
        setHistory((h) => [...h, event]);
      }
      await refreshSession(session.session_id);
      return event;
    } catch (e) {
      setError(e.message);
      return null;
    }
  }, [session, refreshSession]);

  const pause = useCallback(async () => {
    if (!session) return;
    autoRunRef.current = false;
    setRunning(false);
    try {
      const info = await api.pauseSession(session.session_id);
      setSession(info);
    } catch (e) {
      setError(e.message);
    }
  }, [session]);

  const resume = useCallback(async () => {
    if (!session) return;
    try {
      const info = await api.resumeSession(session.session_id);
      setSession(info);
    } catch (e) {
      setError(e.message);
    }
  }, [session]);

  const autoRun = useCallback(async (speed = 200) => {
    if (!session) return;
    speedRef.current = speed;
    autoRunRef.current = true;
    setRunning(true);

    const loop = async () => {
      while (autoRunRef.current) {
        const event = await step();
        if (!event) {
          autoRunRef.current = false;
          setRunning(false);
          break;
        }
        await new Promise((r) => setTimeout(r, speedRef.current));
      }
    };
    loop();
  }, [session, step]);

  const stopAutoRun = useCallback(() => {
    autoRunRef.current = false;
    setRunning(false);
  }, []);

  const setSpeed = useCallback((ms) => {
    speedRef.current = ms;
  }, []);

  // WebSocket event handler
  const handleWsEvent = useCallback((msg) => {
    if (msg.event === 'step') {
      setHistory((h) => [...h, msg.data]);
    } else if (msg.event === 'peer_request') {
      setPeerRequest(msg.data);
    } else if (msg.event === 'completed') {
      setRunning(false);
      autoRunRef.current = false;
      refreshSession(msg.session_id);
    } else if (msg.event === 'error') {
      setError(msg.data?.message || 'WebSocket error');
    }
  }, [refreshSession]);

  const clearPeerRequest = useCallback(() => {
    setPeerRequest(null);
  }, []);

  return {
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
  };
}
