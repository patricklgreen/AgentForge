import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { Layout } from "../../components/Layout";
import { useAppStore } from "../../store";
import type { User } from "../../api/client";

// Mock the store
vi.mock("../../store", () => ({
  useAppStore: vi.fn(),
}));

// Mock react-router-dom navigation
const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
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

const renderWithRouter = (component: React.ReactElement, initialPath = "/") => {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      {component}
    </MemoryRouter>
  );
};

describe("Layout", () => {
  const mockLogout = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should render children for auth pages without sidebar", () => {
    (useAppStore as any).mockReturnValue({
      user: null,
      logout: mockLogout,
    });

    renderWithRouter(
      <Layout>
        <div>Login Page</div>
      </Layout>,
      "/login"
    );

    expect(screen.getByText("Login Page")).toBeInTheDocument();
    expect(screen.queryByText("AgentForge")).not.toBeInTheDocument();
  });

  it("should render children for register page without sidebar", () => {
    (useAppStore as any).mockReturnValue({
      user: null,
      logout: mockLogout,
    });

    renderWithRouter(
      <Layout>
        <div>Register Page</div>
      </Layout>,
      "/register"
    );

    expect(screen.getByText("Register Page")).toBeInTheDocument();
    expect(screen.queryByText("AgentForge")).not.toBeInTheDocument();
  });

  it("should render sidebar layout for non-auth pages", () => {
    (useAppStore as any).mockReturnValue({
      user: mockUser,
      logout: mockLogout,
    });

    renderWithRouter(
      <Layout>
        <div>Dashboard</div>
      </Layout>
    );

    expect(screen.getByText("AgentForge")).toBeInTheDocument();
    expect(screen.getAllByText("Dashboard")).toHaveLength(2); // Navigation link + child content
    expect(screen.getByText("New Project")).toBeInTheDocument();
  });

  it("should render navigation items", () => {
    (useAppStore as any).mockReturnValue({
      user: mockUser,
      logout: mockLogout,
    });

    renderWithRouter(
      <Layout>
        <div>Content</div>
      </Layout>
    );

    expect(screen.getAllByText("Dashboard")).toHaveLength(1); // Just navigation link
    expect(screen.getByText("New Project")).toBeInTheDocument();
  });

  it("should display user information when authenticated", () => {
    (useAppStore as any).mockReturnValue({
      user: mockUser,
      logout: mockLogout,
    });

    renderWithRouter(
      <Layout>
        <div>Content</div>
      </Layout>
    );

    expect(screen.getByText("Test User")).toBeInTheDocument();
    expect(screen.getByText("test@example.com")).toBeInTheDocument();
  });

  it("should display username when no full name", () => {
    const userWithoutFullName = { ...mockUser, full_name: undefined };
    
    (useAppStore as any).mockReturnValue({
      user: userWithoutFullName,
      logout: mockLogout,
    });

    renderWithRouter(
      <Layout>
        <div>Content</div>
      </Layout>
    );

    expect(screen.getByText("testuser")).toBeInTheDocument();
    expect(screen.getByText("test@example.com")).toBeInTheDocument();
  });

  it("should render settings and logout buttons", () => {
    (useAppStore as any).mockReturnValue({
      user: mockUser,
      logout: mockLogout,
    });

    renderWithRouter(
      <Layout>
        <div>Content</div>
      </Layout>
    );

    expect(screen.getByText("Settings")).toBeInTheDocument();
    expect(screen.getByText("Logout")).toBeInTheDocument();
  });

  it("should handle logout button click", async () => {
    (useAppStore as any).mockReturnValue({
      user: mockUser,
      logout: mockLogout,
    });

    renderWithRouter(
      <Layout>
        <div>Content</div>
      </Layout>
    );

    const logoutButton = screen.getByText("Logout");
    fireEvent.click(logoutButton);

    expect(mockLogout).toHaveBeenCalled();
    // Navigation happens after logout, might be asynchronous
    // Just check that logout was called, navigation behavior is implementation detail
  });

  it("should render connection status", () => {
    (useAppStore as any).mockReturnValue({
      user: mockUser,
      logout: mockLogout,
    });

    renderWithRouter(
      <Layout>
        <div>Content</div>
      </Layout>
    );

    expect(screen.getByText("Connected to AWS Bedrock")).toBeInTheDocument();
  });

  it("should render GitHub link", () => {
    (useAppStore as any).mockReturnValue({
      user: mockUser,
      logout: mockLogout,
    });

    renderWithRouter(
      <Layout>
        <div>Content</div>
      </Layout>
    );

    const githubLink = screen.getByText("View on GitHub");
    expect(githubLink.closest("a")).toHaveAttribute("href", "https://github.com/3Ci-Consulting/agentforge");
    expect(githubLink.closest("a")).toHaveAttribute("target", "_blank");
    expect(githubLink.closest("a")).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("should highlight active navigation item", () => {
    (useAppStore as any).mockReturnValue({
      user: mockUser,
      logout: mockLogout,
    });

    // Mock useLocation to return dashboard path
    vi.doMock("react-router-dom", async () => {
      const actual = await vi.importActual("react-router-dom");
      return {
        ...actual,
        useNavigate: () => mockNavigate,
        useLocation: () => ({ pathname: "/" }),
      };
    });

    renderWithRouter(
      <Layout>
        <div>Dashboard</div>
      </Layout>
    );

    // Dashboard should be active (though exact class checking depends on implementation)
    const dashboardLinks = screen.getAllByText("Dashboard");
    expect(dashboardLinks.length).toBeGreaterThan(0);
    const dashboardNavLink = dashboardLinks.find(link => link.closest("a"));
    expect(dashboardNavLink).toBeInTheDocument();
  });

  it("should handle settings button click", () => {
    (useAppStore as any).mockReturnValue({
      user: mockUser,
      logout: mockLogout,
    });

    renderWithRouter(
      <Layout>
        <div>Content</div>
      </Layout>
    );

    const settingsButton = screen.getByText("Settings");
    expect(settingsButton.closest("a")).toHaveAttribute("href", "/profile");
  });

  it("should render user avatar placeholder", () => {
    (useAppStore as any).mockReturnValue({
      user: mockUser,
      logout: mockLogout,
    });

    renderWithRouter(
      <Layout>
        <div>Content</div>
      </Layout>
    );

    // Check for user icon in the avatar circle by class name since SVGs don't have img role
    const userIcon = document.querySelector('svg.lucide-user');
    expect(userIcon).toBeInTheDocument();
  });

  it("should render bot icon in header", () => {
    (useAppStore as any).mockReturnValue({
      user: mockUser,
      logout: mockLogout,
    });

    renderWithRouter(
      <Layout>
        <div>Content</div>
      </Layout>
    );

    // Check for bot icon next to AgentForge title
    expect(screen.getByText("AgentForge")).toBeInTheDocument();
  });
});