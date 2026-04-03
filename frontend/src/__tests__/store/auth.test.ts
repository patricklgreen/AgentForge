import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { act } from "react";
import { useAppStore } from "../../store";
import type { User } from "../../api/client";

// Mock the API client
vi.mock("../../api/client", () => ({
  authApi: {
    login: vi.fn(),
    register: vi.fn(),
    me: vi.fn(),
    logout: vi.fn(),
  },
  tokenService: {
    getToken: vi.fn(),
    getRefreshToken: vi.fn(),
    setTokens: vi.fn(),
    clearTokens: vi.fn(),
  },
}));

const mockUser: User = {
  id: "user-123",
  email: "test@example.com",
  username: "testuser",
  full_name: "Test User",
  role: "user",
  is_active: true,
  is_verified: true,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
};

describe("useAppStore Authentication", () => {
  beforeEach(() => {
    // Clear the store before each test
    const { getState } = useAppStore;
    act(() => {
      getState().setUser(null);
    });
    vi.clearAllMocks();
  });

  it("should initialize with no authenticated user", () => {
    const { result } = renderHook(() => useAppStore());
    
    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.isLoading).toBe(false);
  });

  it("should handle successful login", async () => {
    const { authApi, tokenService } = await import("../../api/client");
    
    // Mock successful login response
    const loginResponse = {
      access_token: "access-token-123",
      refresh_token: "refresh-token-123",
      token_type: "bearer",
      expires_in: 3600,
      user: mockUser,
    };
    
    (authApi.login as any).mockResolvedValue(loginResponse);

    const { result } = renderHook(() => useAppStore());

    await act(async () => {
      await result.current.login({
        email: "test@example.com",
        password: "password123",
      });
    });

    expect(authApi.login).toHaveBeenCalledWith({
      email: "test@example.com",
      password: "password123",
    });
    expect(tokenService.setTokens).toHaveBeenCalledWith(
      "access-token-123",
      "refresh-token-123"
    );
    expect(result.current.user).toEqual(mockUser);
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.isLoading).toBe(false);
  });

  it("should handle login failure", async () => {
    const { authApi } = await import("../../api/client");
    
    (authApi.login as any).mockRejectedValue(new Error("Invalid credentials"));

    const { result } = renderHook(() => useAppStore());

    await act(async () => {
      try {
        await result.current.login({
          email: "test@example.com",
          password: "wrongpassword",
        });
      } catch (error) {
        expect(error).toBeInstanceOf(Error);
      }
    });

    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.isLoading).toBe(false);
  });

  it("should handle successful registration", async () => {
    const { authApi } = await import("../../api/client");
    
    (authApi.register as any).mockResolvedValue(mockUser);

    const { result } = renderHook(() => useAppStore());

    await act(async () => {
      await result.current.register({
        email: "test@example.com",
        username: "testuser",
        password: "password123",
        full_name: "Test User",
      });
    });

    expect(authApi.register).toHaveBeenCalledWith({
      email: "test@example.com",
      username: "testuser",
      password: "password123",
      full_name: "Test User",
    });
    expect(result.current.isLoading).toBe(false);
  });

  it("should handle logout", async () => {
    const { authApi, tokenService } = await import("../../api/client");
    
    (authApi.logout as any).mockResolvedValue(undefined);

    const { result } = renderHook(() => useAppStore());

    // Set initial authenticated state
    act(() => {
      result.current.setUser(mockUser);
    });

    expect(result.current.isAuthenticated).toBe(true);

    await act(async () => {
      await result.current.logout();
    });

    expect(authApi.logout).toHaveBeenCalled();
    expect(tokenService.clearTokens).toHaveBeenCalled();
    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.projects).toEqual([]);
    expect(result.current.activeRun).toBeNull();
  });

  it("should handle checkAuth with valid token", async () => {
    const { authApi, tokenService } = await import("../../api/client");
    
    (tokenService.getToken as any).mockReturnValue("valid-token");
    (authApi.me as any).mockResolvedValue(mockUser);

    const { result } = renderHook(() => useAppStore());

    await act(async () => {
      await result.current.checkAuth();
    });

    expect(authApi.me).toHaveBeenCalled();
    expect(result.current.user).toEqual(mockUser);
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.isLoading).toBe(false);
  });

  it("should handle checkAuth with no token", async () => {
    const { tokenService } = await import("../../api/client");
    
    (tokenService.getToken as any).mockReturnValue(null);

    const { result } = renderHook(() => useAppStore());

    await act(async () => {
      await result.current.checkAuth();
    });

    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
  });

  it("should handle checkAuth with invalid token", async () => {
    const { authApi, tokenService } = await import("../../api/client");
    
    (tokenService.getToken as any).mockReturnValue("invalid-token");
    (authApi.me as any).mockRejectedValue(new Error("Invalid token"));

    const { result } = renderHook(() => useAppStore());

    await act(async () => {
      await result.current.checkAuth();
    });

    expect(tokenService.clearTokens).toHaveBeenCalled();
    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.isLoading).toBe(false);
  });

  it("should set user and authentication state", () => {
    const { result } = renderHook(() => useAppStore());

    act(() => {
      result.current.setUser(mockUser);
    });

    expect(result.current.user).toEqual(mockUser);
    expect(result.current.isAuthenticated).toBe(true);

    act(() => {
      result.current.setUser(null);
    });

    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
  });
});