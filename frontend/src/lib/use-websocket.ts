"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";

export interface WebSocketMessage<T = unknown> {
  type: string;
  channel?: string;
  data?: T;
  timestamp?: string;
}

export type ConnectionState = "connecting" | "connected" | "disconnected" | "error";

interface UseWebSocketOptions<T = unknown> {
  channel?: "tasks" | "workers" | "metrics" | "live" | "queues";
  enabled?: boolean;
  tenantId?: string;
  token?: string;
  onMessage?: (message: WebSocketMessage<T>) => void;
  autoInvalidate?: boolean;
}

export function useWebSocketSubscription<T = unknown>({
  channel = "live",
  enabled = true,
  tenantId,
  token,
  onMessage,
  autoInvalidate = true,
}: UseWebSocketOptions<T> = {}) {
  const [connectionState, setConnectionState] = useState<ConnectionState>("disconnected");
  const [lastEvent, setLastEvent] = useState<WebSocketMessage<T> | null>(null);
  const [error, setError] = useState<Event | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const heartbeatIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const intentionalDisconnectRef = useRef(false);
  const queryClient = useQueryClient();

  const getWsUrl = useCallback(() => {
    const params = new URLSearchParams();
    if (tenantId) params.set("tenant_id", tenantId);
    if (token) params.set("token", token);
    const qs = params.toString() ? `?${params.toString()}` : "";

    if (process.env.NEXT_PUBLIC_WS_URL) {
      return `${process.env.NEXT_PUBLIC_WS_URL}/ws/${channel}${qs}`;
    }
    if (typeof window !== "undefined") {
      const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host =
        window.location.hostname === "localhost"
          ? "127.0.0.1"
          : window.location.hostname;
      return `${proto}//${host}:8000/api/v1/ws/${channel}${qs}`;
    }
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1";
    const wsBase = apiBase.replace(/^http:/, "ws:").replace(/^https:/, "wss:");
    return `${wsBase}/ws/${channel}${qs}`;
  }, [channel, tenantId, token]);

  const handleMessage = useCallback(
    (event: MessageEvent) => {
      try {
        if (event.data === "pong") return;
        const parsed: WebSocketMessage<T> = JSON.parse(event.data);
        if (parsed.type === "pong") return;
        setLastEvent(parsed);

        if (onMessage) {
          onMessage(parsed);
        }

        // Automatic TanStack Query Cache Invalidation on live events
        if (autoInvalidate && parsed.type) {
          if (parsed.type.startsWith("task.")) {
            queryClient.invalidateQueries({ queryKey: ["tasks"] });
            queryClient.invalidateQueries({ queryKey: ["analytics"] });
          } else if (parsed.type.startsWith("worker.")) {
            queryClient.invalidateQueries({ queryKey: ["workers"] });
            queryClient.invalidateQueries({ queryKey: ["analytics"] });
          } else if (parsed.type.startsWith("queue.")) {
            queryClient.invalidateQueries({ queryKey: ["queues"] });
          } else if (parsed.type.startsWith("metrics.")) {
            queryClient.invalidateQueries({ queryKey: ["analytics"] });
          }
        }
      } catch {
        // Ignored or non-JSON keepalive
      }
    },
    [autoInvalidate, onMessage, queryClient]
  );

  const connect = useCallback(() => {
    if (!enabled || typeof window === "undefined") return;

    if (socketRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    intentionalDisconnectRef.current = false;
    setConnectionState("connecting");
    const url = getWsUrl();

    try {
      const ws = new WebSocket(url);
      socketRef.current = ws;

      ws.onopen = () => {
        setConnectionState("connected");
        setError(null);
        reconnectAttemptsRef.current = 0;

        // Start heartbeat ping every 20 seconds
        if (heartbeatIntervalRef.current) clearInterval(heartbeatIntervalRef.current);
        heartbeatIntervalRef.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send("ping");
          }
        }, 20000);
      };

      ws.onmessage = handleMessage;

      ws.onerror = (err) => {
        setError(err);
        setConnectionState("error");
      };

      ws.onclose = () => {
        setConnectionState("disconnected");
        if (heartbeatIntervalRef.current) clearInterval(heartbeatIntervalRef.current);

        // Exponential backoff reconnect: 1s, 2s, 4s, 8s, up to 15s
        // Only reconnect if disconnection was unintentional and hook is still enabled
        if (!intentionalDisconnectRef.current && enabled) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 15000);
          reconnectAttemptsRef.current += 1;
          if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        }
      };
    } catch {
      setConnectionState("error");
    }
  }, [enabled, getWsUrl, handleMessage]);

  const disconnect = useCallback(() => {
    intentionalDisconnectRef.current = true;
    if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
    if (heartbeatIntervalRef.current) clearInterval(heartbeatIntervalRef.current);
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }
    setConnectionState("disconnected");
  }, []);

  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    connectionState,
    isConnected: connectionState === "connected",
    isConnecting: connectionState === "connecting",
    lastEvent,
    error,
    reconnect: connect,
    disconnect,
  };
}
