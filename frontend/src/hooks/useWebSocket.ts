import { useEffect, useRef, useCallback } from 'react';

type WsEvent = 'progress' | 'complete' | 'error';
type WsCallback = (data: Record<string, unknown>) => void;

export function useWebSocket(runId: string | null, callbacks: Partial<Record<WsEvent, WsCallback>>) {
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    if (!runId) return;
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//localhost:8000/api/ws/ingestion/${runId}`;

    const ws = new WebSocket(url);
    ws.onopen = () => console.debug('[WS] Connected:', runId);
    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        const handler = callbacks[msg.event as WsEvent];
        handler?.(msg.data);
      } catch { /* ignore parse errors */ }
    };
    ws.onerror = () => console.error('[WS] Error:', runId);
    ws.onclose = () => console.debug('[WS] Closed:', runId);
    wsRef.current = ws;
  }, [runId, callbacks]);

  const disconnect = useCallback(() => {
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  return { disconnect };
}
