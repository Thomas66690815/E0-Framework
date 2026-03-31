import { useRef, useEffect, useCallback } from 'react';
import { connectWebSocket } from '../api';

/**
 * Hook: manages a WebSocket connection to an E₀ session.
 *
 * Returns { send, sendPeerResponse, pause, resume, close, connected }.
 * Automatically reconnects on unexpected close.
 */
export function useWebSocket(sessionId, onEvent) {
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const connectedRef = useRef(false);

  const connect = useCallback(() => {
    if (!sessionId) return;

    wsRef.current = connectWebSocket(sessionId, {
      onEvent: (msg) => {
        connectedRef.current = true;
        onEvent?.(msg);
      },
      onError: () => {
        connectedRef.current = false;
      },
      onClose: () => {
        connectedRef.current = false;
        // Reconnect after 2s unless intentionally closed
        if (sessionId) {
          reconnectTimer.current = setTimeout(connect, 2000);
        }
      },
    });
  }, [sessionId, onEvent]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [connect]);

  return {
    send: (event, data) => wsRef.current?.send(event, data),
    sendPeerResponse: (target) => wsRef.current?.sendPeerResponse(target),
    pause: () => wsRef.current?.pause(),
    resume: () => wsRef.current?.resume(),
    close: () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
      wsRef.current = null;
    },
    get connected() { return connectedRef.current; },
  };
}
