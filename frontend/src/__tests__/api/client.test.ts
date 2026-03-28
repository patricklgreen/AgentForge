import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// ─── RunWebSocket ─────────────────────────────────────────────────────────────

describe("RunWebSocket", () => {
  let mockWsInstance: {
    onopen:    ((e: Event) => void) | null;
    onmessage: ((e: MessageEvent) => void) | null;
    onclose:   ((e: CloseEvent) => void) | null;
    onerror:   ((e: Event) => void) | null;
    close:     ReturnType<typeof vi.fn>;
    readyState: number;
  };

  const MockWebSocket = vi.fn().mockImplementation(() => {
    mockWsInstance = {
      onopen:    null,
      onmessage: null,
      onclose:   null,
      onerror:   null,
      close:     vi.fn(),
      readyState: WebSocket.CONNECTING,
    };
    return mockWsInstance;
  });

  beforeEach(() => {
    vi.stubGlobal("WebSocket", MockWebSocket);
    MockWebSocket.OPEN = 1;
    MockWebSocket.CONNECTING = 0;
    MockWebSocket.CLOSING = 2;
    MockWebSocket.CLOSED = 3;
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    MockWebSocket.mockClear();
  });

  it("connects to the correct WebSocket URL", async () => {
    const { RunWebSocket } = await import("../../api/client");
    const ws = new RunWebSocket("test-run-id-123");
    ws.connect();

    expect(MockWebSocket).toHaveBeenCalledWith(
      expect.stringContaining("test-run-id-123")
    );
  });

  it("dispatches events to type-specific handlers", async () => {
    const { RunWebSocket } = await import("../../api/client");
    const ws = new RunWebSocket("run-id");
    const handler = vi.fn();
    ws.on("agent_start", handler);
    ws.connect();

    const message = { type: "agent_start", agent: "CodeGen", message: "Starting" };
    mockWsInstance.onmessage?.({
      data: JSON.stringify(message),
    } as MessageEvent);

    expect(handler).toHaveBeenCalledWith(message);
  });

  it("dispatches events to wildcard (*) handlers", async () => {
    const { RunWebSocket } = await import("../../api/client");
    const ws = new RunWebSocket("run-id");
    const wildcard = vi.fn();
    ws.on("*", wildcard);
    ws.connect();

    const message = { type: "any_event_type", message: "test" };
    mockWsInstance.onmessage?.({
      data: JSON.stringify(message),
    } as MessageEvent);

    expect(wildcard).toHaveBeenCalledWith(message);
  });

  it("does not dispatch to wrong type handlers", async () => {
    const { RunWebSocket } = await import("../../api/client");
    const ws = new RunWebSocket("run-id");
    const handler = vi.fn();
    ws.on("agent_complete", handler);
    ws.connect();

    mockWsInstance.onmessage?.({
      data: JSON.stringify({ type: "agent_start", message: "Started" }),
    } as MessageEvent);

    expect(handler).not.toHaveBeenCalled();
  });

  it("fires both type-specific and wildcard handlers for the same message", async () => {
    const { RunWebSocket } = await import("../../api/client");
    const ws = new RunWebSocket("run-id");
    const specificHandler = vi.fn();
    const wildcardHandler = vi.fn();
    ws.on("interrupt", specificHandler);
    ws.on("*",         wildcardHandler);
    ws.connect();

    mockWsInstance.onmessage?.({
      data: JSON.stringify({ type: "interrupt", message: "Review needed" }),
    } as MessageEvent);

    expect(specificHandler).toHaveBeenCalledTimes(1);
    expect(wildcardHandler).toHaveBeenCalledTimes(1);
  });

  it("silently ignores invalid JSON messages", async () => {
    const { RunWebSocket } = await import("../../api/client");
    const ws = new RunWebSocket("run-id");
    const handler = vi.fn();
    ws.on("*", handler);
    ws.connect();

    // Should not throw
    mockWsInstance.onmessage?.({ data: "NOT JSON {{{" } as MessageEvent);

    expect(handler).not.toHaveBeenCalled();
  });

  it("removes handlers via off()", async () => {
    const { RunWebSocket } = await import("../../api/client");
    const ws = new RunWebSocket("run-id");
    const handler = vi.fn();
    ws.on("agent_start", handler);
    ws.off("agent_start", handler);
    ws.connect();

    mockWsInstance.onmessage?.({
      data: JSON.stringify({ type: "agent_start", message: "Starting" }),
    } as MessageEvent);

    expect(handler).not.toHaveBeenCalled();
  });

  it("closes the WebSocket on disconnect()", async () => {
    const { RunWebSocket } = await import("../../api/client");
    const ws = new RunWebSocket("run-id");
    ws.connect();
    ws.disconnect();

    expect(mockWsInstance.close).toHaveBeenCalled();
  });

  it("does not reconnect after manual disconnect()", async () => {
    vi.useFakeTimers();
    const { RunWebSocket } = await import("../../api/client");
    const ws = new RunWebSocket("run-id");
    ws.connect();
    ws.disconnect();

    // Simulate connection close
    mockWsInstance.onclose?.({} as CloseEvent);

    vi.advanceTimersByTime(10_000);

    // Should not have created a new connection
    expect(MockWebSocket).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });
});

// ─── projectsApi ─────────────────────────────────────────────────────────────

describe("projectsApi shape", () => {
  it("exports the expected methods", async () => {
    const { projectsApi } = await import("../../api/client");
    expect(typeof projectsApi.create).toBe("function");
    expect(typeof projectsApi.list).toBe("function");
    expect(typeof projectsApi.get).toBe("function");
    expect(typeof projectsApi.startRun).toBe("function");
    expect(typeof projectsApi.listRuns).toBe("function");
    expect(typeof projectsApi.getRun).toBe("function");
    expect(typeof projectsApi.submitFeedback).toBe("function");
    expect(typeof projectsApi.cancelRun).toBe("function");         // ← new
    expect(typeof projectsApi.getRunState).toBe("function");
  });
});

// ─── artifactsApi ─────────────────────────────────────────────────────────────

describe("artifactsApi shape", () => {
  it("exports the expected methods", async () => {
    const { artifactsApi } = await import("../../api/client");
    expect(typeof artifactsApi.list).toBe("function");
    expect(typeof artifactsApi.getContent).toBe("function");
    expect(typeof artifactsApi.getDownloadUrl).toBe("function");
  });
});
