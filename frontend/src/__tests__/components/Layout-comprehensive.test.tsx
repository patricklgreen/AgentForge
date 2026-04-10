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

describe("Layout Component Comprehensive Tests", () => {
  const mockLogout = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("Auth Page Behavior", () => {
    it("should render children for login page without sidebar", () => {
      (useAppStore as any).mockReturnValue({
        user: null,
        logout: mockLogout,
      });

      renderWithRouter(
        <Layout>
          <div>Login Page Content</div>
        </Layout>,
        "/login"
      );

      expect(screen.getByText("Login Page Content")).toBeInTheDocument();
      expect(screen.queryByText("AgentForge")).not.toBeInTheDocument();
      expect(screen.queryByText("Dashboard")).not.toBeInTheDocument();
    });

    it("should render children for register page without sidebar", () => {
      (useAppStore as any).mockReturnValue({
        user: null,
        logout: mockLogout,
      });

      renderWithRouter(
        <Layout>
          <div>Register Page Content</div>
        </Layout>,
        "/register"
      );

      expect(screen.getByText("Register Page Content")).toBeInTheDocument();
      expect(screen.queryByText("AgentForge")).not.toBeInTheDocument();
      expect(screen.queryByText("Dashboard")).not.toBeInTheDocument();
    });
  });

  describe("Dashboard Layout", () => {
    it("should render sidebar layout for dashboard", () => {
      (useAppStore as any).mockReturnValue({
        user: mockUser,
        logout: mockLogout,
      });

      renderWithRouter(
        <Layout>
          <div>Dashboard Content</div>
        </Layout>,
        "/"
      );

      // Should show sidebar elements
      expect(screen.getByText("AgentForge")).toBeInTheDocument();
      expect(screen.getByText("Dashboard")).toBeInTheDocument();
      expect(screen.getByText("New Project")).toBeInTheDocument();
      expect(screen.getByText("Dashboard Content")).toBeInTheDocument();
    });

    it("should render all navigation items", () => {
      (useAppStore as any).mockReturnValue({
        user: mockUser,
        logout: mockLogout,
      });

      renderWithRouter(
        <Layout>
          <div>Content</div>
        </Layout>
      );

      // Check navigation items
      expect(screen.getByText("Dashboard")).toBeInTheDocument();
      expect(screen.getByText("New Project")).toBeInTheDocument();
    });

    it("should highlight active navigation item", () => {
      (useAppStore as any).mockReturnValue({
        user: mockUser,
        logout: mockLogout,
      });

      renderWithRouter(
        <Layout>
          <div>Dashboard Content</div>
        </Layout>,
        "/"
      );

      // Dashboard link should have active styling
      const dashboardLink = screen.getByRole("link", { name: /dashboard/i });
      expect(dashboardLink).toHaveClass("bg-gray-800", "text-white", "border-gray-700");
    });

    it("should show user information in sidebar", () => {
      (useAppStore as any).mockReturnValue({
        user: mockUser,
        logout: mockLogout,
      });

      renderWithRouter(
        <Layout>
          <div>Content</div>
        </Layout>
      );

      // Should show user email and username
      expect(screen.getByText("test@example.com")).toBeInTheDocument();
      expect(screen.getByText("testuser")).toBeInTheDocument();
    });

    it("should show user avatar placeholder", () => {
      (useAppStore as any).mockReturnValue({
        user: mockUser,
        logout: mockLogout,
      });

      renderWithRouter(
        <Layout>
          <div>Content</div>
        </Layout>
      );

      // Should show avatar with initials
      expect(screen.getByText("TU")).toBeInTheDocument(); // Test User initials
    });
  });

  describe("Logout Functionality", () => {
    it("should handle logout button click", async () => {
      (useAppStore as any).mockReturnValue({
        user: mockUser,
        logout: mockLogout,
      });

      mockLogout.mockResolvedValue(undefined);

      renderWithRouter(
        <Layout>
          <div>Content</div>
        </Layout>
      );

      const logoutButton = screen.getByRole("button", { name: /logout/i });
      fireEvent.click(logoutButton);

      expect(mockLogout).toHaveBeenCalled();
      expect(mockNavigate).toHaveBeenCalledWith("/login");
    });

    it("should handle logout errors gracefully", async () => {
      (useAppStore as any).mockReturnValue({
        user: mockUser,
        logout: mockLogout,
      });

      mockLogout.mockRejectedValue(new Error("Logout failed"));

      renderWithRouter(
        <Layout>
          <div>Content</div>
        </Layout>
      );

      const logoutButton = screen.getByRole("button", { name: /logout/i });
      
      // Should not throw even if logout fails
      expect(() => fireEvent.click(logoutButton)).not.toThrow();
    });
  });

  describe("Responsive Behavior", () => {
    it("should render properly on different screen sizes", () => {
      (useAppStore as any).mockReturnValue({
        user: mockUser,
        logout: mockLogout,
      });

      renderWithRouter(
        <Layout>
          <div>Responsive Content</div>
        </Layout>
      );

      // Should have responsive classes
      const sidebar = screen.getByText("AgentForge").closest("div");
      expect(sidebar).toHaveClass("w-64"); // Fixed width sidebar
    });
  });

  describe("User Roles", () => {
    it("should render for admin user", () => {
      const adminUser = { ...mockUser, role: "admin" as const };
      (useAppStore as any).mockReturnValue({
        user: adminUser,
        logout: mockLogout,
      });

      renderWithRouter(
        <Layout>
          <div>Admin Content</div>
        </Layout>
      );

      expect(screen.getByText("Admin Content")).toBeInTheDocument();
      expect(screen.getByText("AgentForge")).toBeInTheDocument();
    });

    it("should render for viewer user", () => {
      const viewerUser = { ...mockUser, role: "viewer" as const };
      (useAppStore as any).mockReturnValue({
        user: viewerUser,
        logout: mockLogout,
      });

      renderWithRouter(
        <Layout>
          <div>Viewer Content</div>
        </Layout>
      );

      expect(screen.getByText("Viewer Content")).toBeInTheDocument();
      expect(screen.getByText("AgentForge")).toBeInTheDocument();
    });
  });

  describe("User State Variants", () => {
    it("should handle user without full name", () => {
      const userWithoutName = { ...mockUser, full_name: null };
      (useAppStore as any).mockReturnValue({
        user: userWithoutName,
        logout: mockLogout,
      });

      renderWithRouter(
        <Layout>
          <div>Content</div>
        </Layout>
      );

      // Should still show username and email
      expect(screen.getByText("testuser")).toBeInTheDocument();
      expect(screen.getByText("test@example.com")).toBeInTheDocument();
    });

    it("should handle unverified user", () => {
      const unverifiedUser = { ...mockUser, is_verified: false };
      (useAppStore as any).mockReturnValue({
        user: unverifiedUser,
        logout: mockLogout,
      });

      renderWithRouter(
        <Layout>
          <div>Content</div>
        </Layout>
      );

      // Should still render layout normally
      expect(screen.getByText("AgentForge")).toBeInTheDocument();
      expect(screen.getByText("Content")).toBeInTheDocument();
    });

    it("should handle inactive user", () => {
      const inactiveUser = { ...mockUser, is_active: false };
      (useAppStore as any).mockReturnValue({
        user: inactiveUser,
        logout: mockLogout,
      });

      renderWithRouter(
        <Layout>
          <div>Content</div>
        </Layout>
      );

      // Should still render layout (authentication handled elsewhere)
      expect(screen.getByText("AgentForge")).toBeInTheDocument();
      expect(screen.getByText("Content")).toBeInTheDocument();
    });
  });

  describe("Navigation Links", () => {
    it("should have correct href attributes", () => {
      (useAppStore as any).mockReturnValue({
        user: mockUser,
        logout: mockLogout,
      });

      renderWithRouter(
        <Layout>
          <div>Content</div>
        </Layout>
      );

      const dashboardLink = screen.getByRole("link", { name: /dashboard/i });
      const newProjectLink = screen.getByRole("link", { name: /new project/i });

      expect(dashboardLink).toHaveAttribute("href", "/");
      expect(newProjectLink).toHaveAttribute("href", "/projects/new");
    });

    it("should highlight active link based on current path", () => {
      (useAppStore as any).mockReturnValue({
        user: mockUser,
        logout: mockLogout,
      });

      renderWithRouter(
        <Layout>
          <div>New Project Content</div>
        </Layout>,
        "/projects/new"
      );

      // New Project link should be active
      const newProjectLink = screen.getByRole("link", { name: /new project/i });
      expect(newProjectLink).toHaveClass("bg-gray-800", "text-white");
    });
  });

  describe("Edge Cases", () => {
    it("should handle null user gracefully", () => {
      (useAppStore as any).mockReturnValue({
        user: null,
        logout: mockLogout,
      });

      renderWithRouter(
        <Layout>
          <div>Content for null user</div>
        </Layout>,
        "/dashboard"
      );

      // Should still show content and sidebar for non-auth pages
      expect(screen.getByText("Content for null user")).toBeInTheDocument();
    });

    it("should handle different path structures", () => {
      (useAppStore as any).mockReturnValue({
        user: mockUser,
        logout: mockLogout,
      });

      renderWithRouter(
        <Layout>
          <div>Project Detail Content</div>
        </Layout>,
        "/projects/123"
      );

      expect(screen.getByText("Project Detail Content")).toBeInTheDocument();
      expect(screen.getByText("AgentForge")).toBeInTheDocument();
    });
  });
});