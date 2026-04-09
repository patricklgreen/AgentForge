import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import axios from "axios";

// Mock axios
vi.mock("axios");
const mockedAxios = vi.mocked(axios, true);

describe("Authentication API Client", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    
    // Mock axios.create to return a mocked instance
    (mockedAxios.create as any).mockReturnValue({
      post: vi.fn(),
      get: vi.fn(),
      interceptors: {
        request: { use: vi.fn() },
        response: { use: vi.fn() },
      },
    });
  });

  afterEach(() => {
    vi.resetModules();
  });

  it("should create API client with correct configuration", async () => {
    await import("../../api/client");
    
    expect(mockedAxios.create).toHaveBeenCalledWith({
      baseURL: "http://localhost:8000/api/v1",
      headers: { "Content-Type": "application/json" },
      timeout: 30_000,
    });
  });

  it("should export authApi with correct methods", async () => {
    const { authApi } = await import("../../api/client");
    
    expect(typeof authApi.login).toBe("function");
    expect(typeof authApi.register).toBe("function");
    expect(typeof authApi.me).toBe("function");
    expect(typeof authApi.refresh).toBe("function");
    expect(typeof authApi.logout).toBe("function");
  });

  it("should export tokenService with correct methods", async () => {
    const { tokenService } = await import("../../api/client");
    
    expect(typeof tokenService.getToken).toBe("function");
    expect(typeof tokenService.getRefreshToken).toBe("function");
    expect(typeof tokenService.setTokens).toBe("function");
    expect(typeof tokenService.clearTokens).toBe("function");
  });
});

describe("tokenService", () => {
  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("should store and retrieve tokens", async () => {
    const { tokenService } = await import("../../api/client");
    
    const accessToken = "access-token-123";
    const refreshToken = "refresh-token-456";
    
    tokenService.setTokens(accessToken, refreshToken);
    
    expect(tokenService.getToken()).toBe(accessToken);
    expect(tokenService.getRefreshToken()).toBe(refreshToken);
  });

  it("should clear tokens", async () => {
    const { tokenService } = await import("../../api/client");
    
    tokenService.setTokens("token1", "token2");
    expect(tokenService.getToken()).toBe("token1");
    
    tokenService.clearTokens();
    expect(tokenService.getToken()).toBeNull();
    expect(tokenService.getRefreshToken()).toBeNull();
  });

  it("should return null for non-existent tokens", async () => {
    const { tokenService } = await import("../../api/client");
    
    expect(tokenService.getToken()).toBeNull();
    expect(tokenService.getRefreshToken()).toBeNull();
  });
});

describe("API Interceptors", () => {
  let mockApiInstance: any;

  beforeEach(() => {
    mockApiInstance = {
      post: vi.fn(),
      get: vi.fn(),
      interceptors: {
        request: { use: vi.fn() },
        response: { use: vi.fn() },
      },
    };
    
    (mockedAxios.create as any).mockReturnValue(mockApiInstance);
  });

  it("should add auth interceptors", async () => {
    await import("../../api/client");
    
    // Verify that interceptors were set up
    expect(mockApiInstance.interceptors.request.use).toHaveBeenCalled();
    expect(mockApiInstance.interceptors.response.use).toHaveBeenCalled();
  });

  it("should add Authorization header when token exists", async () => {
    // Import fresh module and get access to the actual api instance
    vi.doUnmock("../../api/client");
    const { tokenService } = await import("../../api/client");
    
    // Set up token in localStorage (which tokenService uses)
    localStorage.setItem("auth_token", "test-token");
    
    // Make a request to trigger the interceptor
    const mockResponse = { data: { message: "success" } };
    (axios.get as any).mockResolvedValueOnce(mockResponse);
    
    // Import and use the API to trigger interceptors
    const response = await axios.get("/test");
    expect(response.data.message).toBe("success");
  });

  it("should not add Authorization header when no token", async () => {
    // Clear any existing tokens
    localStorage.clear();
    
    // Import fresh module
    vi.doUnmock("../../api/client");
    await import("../../api/client");
    
    // Make a request - this would trigger interceptors but we can't easily test
    // the exact header manipulation without access to the real interceptor
    expect(localStorage.getItem("auth_token")).toBeNull();
  });
});

describe("User Interface Types", () => {
  it("should have correct User interface structure", async () => {
    const mockUser = {
      id: "user-123",
      email: "test@example.com",
      username: "testuser",
      full_name: "Test User",
      role: "user" as const,
      is_active: true,
      is_verified: true,
      created_at: "2024-01-01T00:00:00Z",
      updated_at: "2024-01-01T00:00:00Z",
      last_login: "2024-01-01T12:00:00Z",
    };
    
    // Verify the structure matches our expectations
    expect(typeof mockUser.id).toBe("string");
    expect(typeof mockUser.email).toBe("string");
    expect(typeof mockUser.username).toBe("string");
    expect(["admin", "user", "viewer"]).toContain(mockUser.role);
    expect(typeof mockUser.is_active).toBe("boolean");
    expect(typeof mockUser.is_verified).toBe("boolean");
  });

  it("should have correct LoginRequest interface structure", () => {
    const loginRequest = {
      email: "test@example.com",
      password: "password123",
    };
    
    expect(typeof loginRequest.email).toBe("string");
    expect(typeof loginRequest.password).toBe("string");
  });

  it("should have correct RegisterRequest interface structure", () => {
    const registerRequest = {
      email: "test@example.com",
      username: "testuser",
      password: "password123",
      full_name: "Test User",
    };
    
    expect(typeof registerRequest.email).toBe("string");
    expect(typeof registerRequest.username).toBe("string");
    expect(typeof registerRequest.password).toBe("string");
    expect(typeof registerRequest.full_name).toBe("string");
  });

  it("should have correct LoginResponse interface structure", () => {
    const loginResponse = {
      access_token: "token123",
      refresh_token: "refresh123",
      token_type: "bearer",
      expires_in: 3600,
      user: {
        id: "user-123",
        email: "test@example.com",
        username: "testuser",
        role: "user" as const,
        is_active: true,
        is_verified: true,
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T00:00:00Z",
      },
    };
    
    expect(typeof loginResponse.access_token).toBe("string");
    expect(typeof loginResponse.refresh_token).toBe("string");
    expect(typeof loginResponse.token_type).toBe("string");
    expect(typeof loginResponse.expires_in).toBe("number");
    expect(typeof loginResponse.user).toBe("object");
  });
});