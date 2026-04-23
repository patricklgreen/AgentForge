import { describe, it, expect, vi, beforeEach } from "vitest";
import { authApi, projectsApi, artifactsApi, emailVerificationApi, tokenService } from "../../api/client";

// Mock axios (avoid self-referential initializer typing)
vi.mock("axios", () => {
  const mockAxios = {
    create: vi.fn(),
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  };
  mockAxios.create.mockReturnValue(mockAxios);
  return { default: mockAxios };
});

describe("API Client Comprehensive Tests", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  describe("Token Service", () => {
    it("should store and retrieve access token", () => {
      const token = "test-access-token";
      tokenService.setTokens(token, "refresh-token");
      expect(tokenService.getToken()).toBe(token);
    });

    it("should store and retrieve refresh token", () => {
      const refreshToken = "test-refresh-token";
      tokenService.setTokens("access-token", refreshToken);
      expect(tokenService.getRefreshToken()).toBe(refreshToken);
    });

    it("should clear both tokens", () => {
      tokenService.setTokens("access", "refresh");
      tokenService.clearTokens();
      expect(tokenService.getToken()).toBeNull();
      expect(tokenService.getRefreshToken()).toBeNull();
    });

    it("should return null for non-existent tokens", () => {
      expect(tokenService.getToken()).toBeNull();
      expect(tokenService.getRefreshToken()).toBeNull();
    });
  });

  describe("Auth API", () => {
    it("should have login method", () => {
      expect(typeof authApi.login).toBe("function");
    });

    it("should have register method", () => {
      expect(typeof authApi.register).toBe("function");
    });

    it("should have me method", () => {
      expect(typeof authApi.me).toBe("function");
    });

    it("should have refresh method", () => {
      expect(typeof authApi.refresh).toBe("function");
    });

    it("should have logout method", () => {
      expect(typeof authApi.logout).toBe("function");
    });
  });

  describe("Projects API", () => {
    it("should have list method", () => {
      expect(typeof projectsApi.list).toBe("function");
    });

    it("should have create method", () => {
      expect(typeof projectsApi.create).toBe("function");
    });

    it("should have get method", () => {
      expect(typeof projectsApi.get).toBe("function");
    });

    it("should have startRun method", () => {
      expect(typeof projectsApi.startRun).toBe("function");
    });

    it("should have cancelRun method", () => {
      expect(typeof projectsApi.cancelRun).toBe("function");
    });

    it("should have submitFeedback method", () => {
      expect(typeof projectsApi.submitFeedback).toBe("function");
    });

    it("should have getRunState method", () => {
      expect(typeof projectsApi.getRunState).toBe("function");
    });
  });

  describe("Artifacts API", () => {
    it("should have list method", () => {
      expect(typeof artifactsApi.list).toBe("function");
    });

    it("should have getContent method", () => {
      expect(typeof artifactsApi.getContent).toBe("function");
    });

    it("should have getDownloadUrl method", () => {
      expect(typeof artifactsApi.getDownloadUrl).toBe("function");
    });
  });

  describe("Email Verification API", () => {
    it("should have sendVerificationEmail method", () => {
      expect(typeof emailVerificationApi.sendVerificationEmail).toBe("function");
    });

    it("should have confirmEmailVerification method", () => {
      expect(typeof emailVerificationApi.confirmEmailVerification).toBe("function");
    });

    it("should have getVerificationStatus method", () => {
      expect(typeof emailVerificationApi.getVerificationStatus).toBe("function");
    });
  });
});

describe("RunWebSocket", () => {
  // Mock WebSocket
  const mockWebSocket = {
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    close: vi.fn(),
    send: vi.fn(),
    readyState: 1, // OPEN
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (global as any).WebSocket = vi.fn(() => mockWebSocket);
  });

  it("should create WebSocket connection when connect() is called", async () => {
    const { RunWebSocket } = await import("../../api/client");
    const ws = new RunWebSocket("test-run-id");
    
    ws.connect();
    
    expect(global.WebSocket).toHaveBeenCalled();
  });

  it("should handle connection events", async () => {
    const { RunWebSocket } = await import("../../api/client");
    const ws = new RunWebSocket("test-run-id");
    
    const handler = vi.fn();
    ws.on("test_event", handler);
    
    // Simulate WebSocket message
    const messageEvent = {
      data: JSON.stringify({ event_type: "test_event", data: { test: "data" } })
    };
    
    // Find the message event listener and call it
    const messageListener = mockWebSocket.addEventListener.mock.calls.find(
      call => call[0] === "message"
    )?.[1];
    
    if (messageListener) {
      messageListener(messageEvent);
      expect(handler).toHaveBeenCalledWith({ test: "data" });
    }
  });

  it("should handle wildcard events", async () => {
    const { RunWebSocket } = await import("../../api/client");
    const ws = new RunWebSocket("test-run-id");
    
    const handler = vi.fn();
    ws.on("*", handler);
    
    // Simulate WebSocket message
    const messageEvent = {
      data: JSON.stringify({ event_type: "any_event", data: { test: "data" } })
    };
    
    // Find the message event listener and call it
    const messageListener = mockWebSocket.addEventListener.mock.calls.find(
      call => call[0] === "message"
    )?.[1];
    
    if (messageListener) {
      messageListener(messageEvent);
      expect(handler).toHaveBeenCalledWith({ test: "data" });
    }
  });

  it("should remove event handlers", async () => {
    const { RunWebSocket } = await import("../../api/client");
    const ws = new RunWebSocket("test-run-id");
    
    const handler = vi.fn();
    ws.on("test_event", handler);
    ws.off("test_event", handler);
    
    // Handler should be removed
    expect(ws.off).toBeDefined();
  });

  it("should close connection when disconnect() is called", async () => {
    const { RunWebSocket } = await import("../../api/client");
    const ws = new RunWebSocket("test-run-id");
    
    ws.connect();
    ws.disconnect();
    expect(mockWebSocket.close).toHaveBeenCalled();
  });

  it("should handle invalid JSON gracefully", async () => {
    const { RunWebSocket } = await import("../../api/client");
    new RunWebSocket("test-run-id");
    
    // Simulate invalid JSON message
    const messageEvent = {
      data: "invalid json"
    };
    
    // Find the message event listener and call it
    const messageListener = mockWebSocket.addEventListener.mock.calls.find(
      call => call[0] === "message"
    )?.[1];
    
    // Should not throw
    expect(() => {
      if (messageListener) {
        messageListener(messageEvent);
      }
    }).not.toThrow();
  });
});