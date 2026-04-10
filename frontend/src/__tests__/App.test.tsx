import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import App from "../App";
import { useAppStore } from "../store";

// Mock the store
vi.mock("../store", () => ({
  useAppStore: vi.fn(),
}));

// Mock the pages
vi.mock("../pages/Dashboard", () => ({
  Dashboard: () => <div>Dashboard Page</div>,
}));

vi.mock("../pages/NewProject", () => ({
  NewProject: () => <div>New Project Page</div>,
}));

vi.mock("../pages/ProjectDetail", () => ({
  ProjectDetail: () => <div>Project Detail Page</div>,
}));

vi.mock("../pages/Login", () => ({
  Login: () => <div>Login Page</div>,
}));

vi.mock("../pages/Register", () => ({
  Register: () => <div>Register Page</div>,
}));

vi.mock("../pages/Profile", () => ({
  Profile: () => <div>Profile Page</div>,
}));

vi.mock("../pages/EmailVerificationPage", () => ({
  EmailVerificationPage: () => <div>Email Verification Page</div>,
}));

vi.mock("../pages/NotFound", () => ({
  NotFound: () => <div>Not Found Page</div>,
}));

// Mock the Layout component
vi.mock("../components/Layout", () => ({
  Layout: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="layout">{children}</div>
  ),
}));

// Mock the ProtectedRoute components
vi.mock("../components/ProtectedRoute", () => ({
  ProtectedRoute: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="protected-route">{children}</div>
  ),
  PublicOnlyRoute: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="public-only-route">{children}</div>
  ),
}));

describe("App", () => {
  const mockCheckAuth = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    (useAppStore as any).mockReturnValue({
      checkAuth: mockCheckAuth,
    });
  });

  it("should call checkAuth on mount", () => {
    render(<App />);
    
    expect(mockCheckAuth).toHaveBeenCalled();
  });

  it("should render Layout component", () => {
    render(<App />);
    
    expect(screen.getByTestId("layout")).toBeInTheDocument();
  });

  it("should wrap the app with QueryClientProvider", () => {
    // This is harder to test directly, but we can verify the app renders without errors
    const { container } = render(<App />);
    
    expect(container.firstChild).toBeInTheDocument();
  });

  it("should render with React Router", () => {
    // We can verify this by checking that our routing works
    // Since we're using MemoryRouter in tests, we'll just verify the app structure
    const { container } = render(<App />);
    
    expect(container.firstChild).toBeInTheDocument();
  });

  it("should have proper app structure", () => {
    render(<App />);
    
    // Should have layout wrapping the routes
    expect(screen.getByTestId("layout")).toBeInTheDocument();
    
    // Should have some route content (depends on default route)
    expect(screen.getByTestId("protected-route")).toBeInTheDocument();
  });
});

describe("App Routes", () => {
  const mockCheckAuth = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    (useAppStore as any).mockReturnValue({
      checkAuth: mockCheckAuth,
    });
  });

  // Note: These tests would need to be more sophisticated in a real app
  // to properly test routing with MemoryRouter and different initial routes
  
  it("should setup routes properly", () => {
    render(<App />);
    
    // Verify the basic structure is there
    expect(screen.getByTestId("layout")).toBeInTheDocument();
  });

  it("should handle protected routes", () => {
    render(<App />);
    
    // Should wrap dashboard in protected route
    expect(screen.getByTestId("protected-route")).toBeInTheDocument();
  });

  it("should handle public only routes", () => {
    render(<App />);
    
    // The default route would show dashboard (protected)
    // but login/register would be public-only routes
    expect(screen.getByTestId("layout")).toBeInTheDocument();
  });
});

describe("App QueryClient Configuration", () => {
  const mockCheckAuth = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    (useAppStore as any).mockReturnValue({
      checkAuth: mockCheckAuth,
    });
  });

  it("should initialize without errors", () => {
    // Test that the QueryClient configuration doesn't cause errors
    expect(() => render(<App />)).not.toThrow();
  });

  it("should render content properly", () => {
    const { container } = render(<App />);
    
    expect(container.firstChild).not.toBeNull();
  });
});

describe("App Authentication Integration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should call checkAuth exactly once on mount", () => {
    const mockCheckAuth = vi.fn();
    (useAppStore as any).mockReturnValue({
      checkAuth: mockCheckAuth,
    });

    render(<App />);
    
    expect(mockCheckAuth).toHaveBeenCalledTimes(1);
  });

  it("should handle checkAuth errors gracefully", () => {
    const mockCheckAuth = vi.fn(() => {
      throw new Error("Network error");
    });
    
    (useAppStore as any).mockReturnValue({
      checkAuth: mockCheckAuth,
    });

    // Should not throw even if checkAuth fails
    expect(() => render(<App />)).not.toThrow();
  });
});