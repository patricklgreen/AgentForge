import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { ProtectedRoute, PublicOnlyRoute } from "../../components/ProtectedRoute";
import { useAppStore } from "../../store";
import type { User } from "../../api/client";

// Mock the store
vi.mock("../../store", () => ({
  useAppStore: vi.fn(),
}));

// Mock react-router-dom
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    Navigate: ({ to, state }: { to: string; state?: any }) => (
      <div data-testid="navigate" data-to={to} data-state={JSON.stringify(state)} />
    ),
    useLocation: () => ({ pathname: "/dashboard", state: null }),
  };
});

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

const renderWithRouter = (component: React.ReactElement) => {
  return render(
    <MemoryRouter>
      {component}
    </MemoryRouter>
  );
};

describe("ProtectedRoute", () => {
  const mockCheckAuth = vi.fn();
  
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should show loading spinner while checking auth", () => {
    (useAppStore as any).mockReturnValue({
      isAuthenticated: false,
      user: null,
      isLoading: true,
      checkAuth: mockCheckAuth,
    });

    renderWithRouter(
      <ProtectedRoute>
        <div>Protected Content</div>
      </ProtectedRoute>
    );

    // Look for the loading spinner element directly
    const spinner = document.querySelector('.animate-spin');
    expect(spinner).toBeInTheDocument();
    expect(screen.queryByText("Protected Content")).not.toBeInTheDocument();
  });

  it("should redirect to login when not authenticated", () => {
    (useAppStore as any).mockReturnValue({
      isAuthenticated: false,
      user: null,
      isLoading: false,
      checkAuth: mockCheckAuth,
    });

    renderWithRouter(
      <ProtectedRoute>
        <div>Protected Content</div>
      </ProtectedRoute>
    );

    const navigate = screen.getByTestId("navigate");
    expect(navigate).toHaveAttribute("data-to", "/login");
    
    // Parse the JSON to check the from property
    const stateAttr = navigate.getAttribute("data-state");
    const state = stateAttr ? JSON.parse(stateAttr) : null;
    expect(state).toHaveProperty("from");
    expect(state.from).toHaveProperty("pathname", "/dashboard");
    
    expect(screen.queryByText("Protected Content")).not.toBeInTheDocument();
  });

  it("should render children when authenticated", () => {
    (useAppStore as any).mockReturnValue({
      isAuthenticated: true,
      user: mockUser,
      isLoading: false,
      checkAuth: mockCheckAuth,
    });

    renderWithRouter(
      <ProtectedRoute>
        <div>Protected Content</div>
      </ProtectedRoute>
    );

    expect(screen.getByText("Protected Content")).toBeInTheDocument();
  });

  it("should call checkAuth when user is null and not loading", async () => {
    (useAppStore as any).mockReturnValue({
      isAuthenticated: false,
      user: null,
      isLoading: false,
      checkAuth: mockCheckAuth,
    });

    renderWithRouter(
      <ProtectedRoute>
        <div>Protected Content</div>
      </ProtectedRoute>
    );

    await waitFor(() => {
      expect(mockCheckAuth).toHaveBeenCalled();
    });
  });

  it("should handle role-based access - user can access user role", () => {
    (useAppStore as any).mockReturnValue({
      isAuthenticated: true,
      user: mockUser,
      isLoading: false,
      checkAuth: mockCheckAuth,
    });

    renderWithRouter(
      <ProtectedRoute requireRole="user">
        <div>User Content</div>
      </ProtectedRoute>
    );

    expect(screen.getByText("User Content")).toBeInTheDocument();
  });

  it("should handle role-based access - user can access viewer role", () => {
    (useAppStore as any).mockReturnValue({
      isAuthenticated: true,
      user: mockUser,
      isLoading: false,
      checkAuth: mockCheckAuth,
    });

    renderWithRouter(
      <ProtectedRoute requireRole="viewer">
        <div>Viewer Content</div>
      </ProtectedRoute>
    );

    expect(screen.getByText("Viewer Content")).toBeInTheDocument();
  });

  it("should handle role-based access - user cannot access admin role", () => {
    (useAppStore as any).mockReturnValue({
      isAuthenticated: true,
      user: mockUser, // user role
      isLoading: false,
      checkAuth: mockCheckAuth,
    });

    renderWithRouter(
      <ProtectedRoute requireRole="admin">
        <div>Admin Content</div>
      </ProtectedRoute>
    );

    expect(screen.getByText("Access Denied")).toBeInTheDocument();
    expect(screen.getByText("You don't have permission to access this page.")).toBeInTheDocument();
    expect(screen.queryByText("Admin Content")).not.toBeInTheDocument();
  });

  it("should handle role-based access - admin can access all roles", () => {
    const adminUser: User = { ...mockUser, role: "admin" };
    
    (useAppStore as any).mockReturnValue({
      isAuthenticated: true,
      user: adminUser,
      isLoading: false,
      checkAuth: mockCheckAuth,
    });

    renderWithRouter(
      <ProtectedRoute requireRole="user">
        <div>User Content</div>
      </ProtectedRoute>
    );

    expect(screen.getByText("User Content")).toBeInTheDocument();
  });

  it("should handle viewer role restrictions", () => {
    const viewerUser: User = { ...mockUser, role: "viewer" };
    
    (useAppStore as any).mockReturnValue({
      isAuthenticated: true,
      user: viewerUser,
      isLoading: false,
      checkAuth: mockCheckAuth,
    });

    renderWithRouter(
      <ProtectedRoute requireRole="user">
        <div>User Content</div>
      </ProtectedRoute>
    );

    expect(screen.getByText("Access Denied")).toBeInTheDocument();
    expect(screen.queryByText("User Content")).not.toBeInTheDocument();
  });
});

describe("PublicOnlyRoute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should show loading spinner while checking auth", () => {
    (useAppStore as any).mockReturnValue({
      isAuthenticated: false,
      user: null,
      isLoading: true,
    });

    renderWithRouter(
      <PublicOnlyRoute>
        <div>Public Content</div>
      </PublicOnlyRoute>
    );

    expect(document.querySelector('.animate-spin')).toBeInTheDocument();
    expect(screen.queryByText("Public Content")).not.toBeInTheDocument();
  });

  it("should render children when not authenticated", () => {
    (useAppStore as any).mockReturnValue({
      isAuthenticated: false,
      user: null,
      isLoading: false,
    });

    renderWithRouter(
      <PublicOnlyRoute>
        <div>Public Content</div>
      </PublicOnlyRoute>
    );

    expect(screen.getByText("Public Content")).toBeInTheDocument();
  });

  it("should redirect to dashboard when authenticated", () => {
    (useAppStore as any).mockReturnValue({
      isAuthenticated: true,
      user: mockUser,
      isLoading: false,
    });

    renderWithRouter(
      <PublicOnlyRoute>
        <div>Public Content</div>
      </PublicOnlyRoute>
    );

    const navigate = screen.getByTestId("navigate");
    expect(navigate).toHaveAttribute("data-to", "/");
    expect(screen.queryByText("Public Content")).not.toBeInTheDocument();
  });
});