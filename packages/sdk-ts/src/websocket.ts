import type { TaskEvent, TaskEventListener } from "./types.js";

export interface WebSocketClientOptions {
  apiUrl: string;
  channel?: "tasks" | "workers";
  reconnect?: boolean;
  maxReconnectAttempts?: number;
  reconnectIntervalMs?: number;
}

export class TaskEngineWebSocket {
  private readonly wsUrl: string;
  private readonly reconnect: boolean;
  private readonly maxReconnectAttempts: number;
  private readonly reconnectIntervalMs: number;
  private socket: any = null;
  private listeners: Map<string, Set<TaskEventListener>> = new Map();
  private reconnectAttempts = 0;
  private closedExplicitly = false;

  constructor(options: WebSocketClientOptions) {
    const base = options.apiUrl.replace(/\/$/, "");
    const protocol = base.startsWith("https") ? "wss" : "ws";
    const host = base.replace(/^https?:\/\//, "");
    const channel = options.channel ?? "tasks";

    this.wsUrl = `${protocol}://${host}/ws/${channel}`;
    this.reconnect = options.reconnect ?? true;
    this.maxReconnectAttempts = options.maxReconnectAttempts ?? 10;
    this.reconnectIntervalMs = options.reconnectIntervalMs ?? 1000;
  }

  public connect(): void {
    this.closedExplicitly = false;
    const WebSocketImpl =
      typeof WebSocket !== "undefined"
        ? WebSocket
        : (globalThis as any).WebSocket;

    if (!WebSocketImpl) {
      throw new Error(
        "WebSocket implementation not found. Please provide a WebSocket polyfill in Node.js environments."
      );
    }

    this.socket = new WebSocketImpl(this.wsUrl);

    this.socket.onmessage = (event: any) => {
      try {
        const payload: TaskEvent = JSON.parse(
          typeof event.data === "string" ? event.data : event.data.toString()
        );
        this.emit(payload.type, payload);
        this.emit("*", payload);
      } catch {}
    };

    this.socket.onclose = () => {
      if (
        !this.closedExplicitly &&
        this.reconnect &&
        this.reconnectAttempts < this.maxReconnectAttempts
      ) {
        this.reconnectAttempts++;
        setTimeout(() => this.connect(), this.reconnectIntervalMs);
      }
    };
  }

  public on(eventType: string, listener: TaskEventListener): void {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, new Set());
    }
    this.listeners.get(eventType)?.add(listener);
  }

  public off(eventType: string, listener: TaskEventListener): void {
    this.listeners.get(eventType)?.delete(listener);
  }

  public emit(eventType: string, event: TaskEvent): void {
    const handlers = this.listeners.get(eventType);
    if (handlers) {
      for (const fn of handlers) {
        fn(event);
      }
    }
  }

  public close(): void {
    this.closedExplicitly = true;
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }
}
