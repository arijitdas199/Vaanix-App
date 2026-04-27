import { useEffect, useRef, useCallback } from "react";
import { getToken, BASE_URL } from "./api";

export type WSMessage = any;

export function useWS(onMessage: (msg: WSMessage) => void, enabled = true) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<any>(null);
  const handlerRef = useRef(onMessage);
  handlerRef.current = onMessage;

  const connect = useCallback(async () => {
    if (!enabled) return;
    const token = await getToken();
    if (!token) return;
    const wsUrl = BASE_URL.replace(/^http/, "ws") + `/api/ws?token=${encodeURIComponent(token)}`;
    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      ws.onmessage = (e) => {
        try {
          const m = JSON.parse(e.data);
          handlerRef.current(m);
        } catch {}
      };
      ws.onclose = () => {
        wsRef.current = null;
        reconnectRef.current = setTimeout(connect, 2500);
      };
      ws.onerror = () => {
        try {
          ws.close();
        } catch {}
      };
    } catch {
      reconnectRef.current = setTimeout(connect, 2500);
    }
  }, [enabled]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      try {
        wsRef.current?.close();
      } catch {}
      wsRef.current = null;
    };
  }, [connect]);

  const send = useCallback((payload: any) => {
    try {
      if (wsRef.current && wsRef.current.readyState === 1) {
        wsRef.current.send(JSON.stringify(payload));
      }
    } catch {}
  }, []);

  return { send };
}
