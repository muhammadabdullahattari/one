import React from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useWebSocketSubscription } from "./use-websocket";
import { LiveStatusIndicator } from "@/components/layout/live-status-indicator";

// Mock WebSocket
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
  static instances: MockWebSocket[] = [];

  url: string;
  readyState: number = 0; // CONNECTING
  onopen: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  sentMessages: string[] = [];

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      if (this.onopen) this.onopen(new Event("open"));
    }, 10);
  }

  send(data: string) {
    this.sentMessages.push(data);
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) this.onclose(new CloseEvent("close"));
  }

  simulateMessage(data: Record<string, unknown> | string) {
    const messageStr = typeof data === "string" ? data : JSON.stringify(data);
    if (this.onmessage) {
      this.onmessage(new MessageEvent("message", { data: messageStr }));
    }
  }
}

describe("WebSocket Real-Time Integration (Phase 11)", () => {
  let queryClient: QueryClient;
  const originalWebSocket = typeof window !== "undefined" ? window.WebSocket : global.WebSocket;

  beforeEach(() => {
    MockWebSocket.instances = [];
    (global as any).WebSocket = MockWebSocket;
    if (typeof window !== "undefined") {
      (window as any).WebSocket = MockWebSocket;
    }
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    });
  });

  afterEach(() => {
    (global as any).WebSocket = originalWebSocket;
    if (typeof window !== "undefined") {
      (window as any).WebSocket = originalWebSocket;
    }
    vi.clearAllTimers();
  });

  it("connects to WebSocket and sets connected state", async () => {
    let hookState: any;
    function TestComponent() {
      hookState = useWebSocketSubscription({ channel: "live" });
      return <div>{hookState.connectionState}</div>;
    }

    render(
      <QueryClientProvider client={queryClient}>
        <TestComponent />
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("connected")).toBeInTheDocument();
    });

    expect(hookState.isConnected).toBe(true);
    expect(MockWebSocket.instances.length).toBeGreaterThan(0);
    expect(MockWebSocket.instances[0].url).toContain("/ws/live");
  });

  it("invalidates TanStack Query cache on incoming real-time events", async () => {
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    function TestComponent() {
      useWebSocketSubscription({ channel: "tasks", autoInvalidate: true });
      return <div>Listening</div>;
    }

    render(
      <QueryClientProvider client={queryClient}>
        <TestComponent />
      </QueryClientProvider>
    );

    await waitFor(() => {
      expect(MockWebSocket.instances.length).toBeGreaterThan(0);
    });

    const ws = MockWebSocket.instances[0];

    // Wait until open
    await waitFor(() => {
      expect(ws.readyState).toBe(WebSocket.OPEN);
    });

    // Simulate task.created event
    await act(async () => {
      ws.simulateMessage({
        type: "task.created",
        data: { task_id: "test-task-123", status: "PENDING" },
      });
    });

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["tasks"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["analytics"] });

    // Simulate worker.updated event
    await act(async () => {
      ws.simulateMessage({
        type: "worker.updated",
        data: { worker_id: "worker-1", status: "active" },
      });
    });

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["workers"] });
  });

  it("renders LiveStatusIndicator correctly across lifecycle", async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <LiveStatusIndicator />
      </QueryClientProvider>
    );

    // Transitions to connected
    await waitFor(() => {
      expect(screen.getByText("Live WS Sync")).toBeInTheDocument();
    });

    const ws = MockWebSocket.instances[0];
    await act(async () => {
      ws.simulateMessage({
        type: "task.succeeded",
        data: { task_id: "task-99" },
      });
    });

    await waitFor(() => {
      expect(screen.getByText("task.succeeded")).toBeInTheDocument();
    });
  });
});
