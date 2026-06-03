"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { API_BASE, WS_BASE } from "../lib/api";
import type { LiveAlert, StreamStatus } from "../lib/types";

type StreamContextValue = {
  streamStatus: StreamStatus;
  liveAlerts: LiveAlert[];
  onLiveMessage: (handler: (payload: LiveAlert & { type?: string }) => void) => () => void;
  refreshAlerts: () => Promise<void>;
};

const StreamContext = createContext<StreamContextValue | null>(null);

export function StreamProvider({ children }: { children: ReactNode }) {
  const [streamStatus, setStreamStatus] = useState<StreamStatus>("connecting");
  const [liveAlerts, setLiveAlerts] = useState<LiveAlert[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptRef = useRef(0);
  const isUnmountedRef = useRef(false);
  const connectionGenRef = useRef(0);
  const lastWsActivityRef = useRef(Date.now());
  const handlersRef = useRef<Set<(payload: LiveAlert & { type?: string }) => void>>(new Set());

  const pushLiveAlert = useCallback((payload: LiveAlert) => {
    const isSmart =
      payload.type === "whale_alert" ||
      (payload as LiveAlert & { alert_passed?: boolean }).alert_passed === true;
    if (!isSmart || !payload.event_id) return;
    setLiveAlerts((prev) => {
      if (prev.some((p) => p.event_id === payload.event_id)) return prev;
      return [payload, ...prev].slice(0, 20);
    });
  }, []);

  const loadRecentAlerts = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/alerts/recent?limit=15`);
      if (!res.ok) return;
      const data = await res.json();
      if (!Array.isArray(data)) return;
      const alerts = data.filter(
        (a: LiveAlert) => a.type === "whale_alert" || a.alert_passed
      );
      if (alerts.length) {
        setLiveAlerts((prev) => {
          const seen = new Set(prev.map((p) => p.event_id));
          const merged = [
            ...alerts.filter((a: LiveAlert) => !seen.has(a.event_id)),
            ...prev,
          ];
          return merged.slice(0, 20);
        });
      }
    } catch {
      /* optional */
    }
  }, []);

  const onLiveMessage = useCallback(
    (handler: (payload: LiveAlert & { type?: string }) => void) => {
      handlersRef.current.add(handler);
      return () => handlersRef.current.delete(handler);
    },
    []
  );

  const dispatch = useCallback(
    (payload: LiveAlert & { type?: string }) => {
      if (payload.type === "heartbeat") return;
      if (payload.type !== "backfill_complete" && payload.type !== "bootstrap_complete") {
        if (payload.event_id) pushLiveAlert(payload as LiveAlert);
      }
      handlersRef.current.forEach((h) => h(payload));
    },
    [pushLiveAlert]
  );

  useEffect(() => {
    isUnmountedRef.current = false;

    const scheduleReconnect = () => {
      if (isUnmountedRef.current) return;
      setStreamStatus("reconnecting");
      const backoffMs = Math.min(15000, 1000 * 2 ** reconnectAttemptRef.current);
      reconnectAttemptRef.current += 1;
      reconnectTimerRef.current = setTimeout(connectSocket, backoffMs);
    };

    const connectSocket = () => {
      if (isUnmountedRef.current) return;
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
      }
      const gen = ++connectionGenRef.current;
      setStreamStatus("connecting");

      const ws = new WebSocket(`${WS_BASE}/api/v1/alerts/ws`);
      wsRef.current = ws;

      ws.onopen = () => {
        if (gen !== connectionGenRef.current) return;
        reconnectAttemptRef.current = 0;
        lastWsActivityRef.current = Date.now();
        setStreamStatus("live");
        loadRecentAlerts();
      };

      ws.onclose = () => {
        if (gen !== connectionGenRef.current || isUnmountedRef.current) return;
        scheduleReconnect();
      };

      ws.onerror = () => {
        if (gen !== connectionGenRef.current) return;
        setStreamStatus("reconnecting");
      };

      ws.onmessage = (event) => {
        if (gen !== connectionGenRef.current) return;
        lastWsActivityRef.current = Date.now();
        setStreamStatus("live");
        try {
          dispatch(JSON.parse(event.data));
        } catch {
          /* ignore */
        }
      };
    };

    connectSocket();

    const watchdog = setInterval(() => {
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      if (Date.now() - lastWsActivityRef.current > 45000) ws.close();
    }, 5000);

    return () => {
      isUnmountedRef.current = true;
      clearInterval(watchdog);
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      connectionGenRef.current += 1;
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [dispatch, loadRecentAlerts]);

  return (
    <StreamContext.Provider
      value={{ streamStatus, liveAlerts, onLiveMessage, refreshAlerts: loadRecentAlerts }}
    >
      {children}
    </StreamContext.Provider>
  );
}

export function useStream() {
  const ctx = useContext(StreamContext);
  if (!ctx) throw new Error("useStream must be used within StreamProvider");
  return ctx;
}
