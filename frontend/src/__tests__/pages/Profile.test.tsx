import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { Profile } from "../../pages/Profile";
import { useAppStore } from "../../store";
import type { User } from "../../api/client";

// Mock the store
vi.mock("../../store", () => ({
  useAppStore: vi.fn(),
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
  last_login: "2024-01-01T12:00:00Z",
};

describe("Profile Page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should show loading message when no user", () => {
    (useAppStore as any).mockReturnValue({
      user: null,
    });

    render(<Profile />);

    expect(screen.getByText("Loading user profile...")).toBeInTheDocument();
  });

  it("should render user profile information", () => {
    (useAppStore as any).mockReturnValue({
      user: mockUser,
    });

    render(<Profile />);

    expect(screen.getByText("User Profile")).toBeInTheDocument();
    expect(screen.getByText("Test User")).toBeInTheDocument();
    expect(screen.getByText("@testuser")).toBeInTheDocument();
    expect(screen.getByText("test@example.com")).toBeInTheDocument();
  });

  it("should display username when no full name", () => {
    const userWithoutFullName = { ...mockUser, full_name: undefined };
    
    (useAppStore as any).mockReturnValue({
      user: userWithoutFullName,
    });

    render(<Profile />);

    expect(screen.getByText("testuser")).toBeInTheDocument();
    expect(screen.getByText("@testuser")).toBeInTheDocument();
  });

  it("should display user role with correct styling", () => {
    (useAppStore as any).mockReturnValue({
      user: mockUser,
    });

    render(<Profile />);

    expect(screen.getByText("User")).toBeInTheDocument();
  });

  it("should display admin role with correct styling", () => {
    const adminUser = { ...mockUser, role: "admin" as const };
    
    (useAppStore as any).mockReturnValue({
      user: adminUser,
    });

    render(<Profile />);

    expect(screen.getByText("Admin")).toBeInTheDocument();
  });

  it("should display viewer role with correct styling", () => {
    const viewerUser = { ...mockUser, role: "viewer" as const };
    
    (useAppStore as any).mockReturnValue({
      user: viewerUser,
    });

    render(<Profile />);

    expect(screen.getByText("Viewer")).toBeInTheDocument();
  });

  it("should display member since date", () => {
    (useAppStore as any).mockReturnValue({
      user: mockUser,
    });

    render(<Profile />);

    expect(screen.getByText(/Member since/)).toBeInTheDocument();
    expect(screen.getByText(/1\/1\/2024/)).toBeInTheDocument();
  });

  it("should display last login when available", () => {
    (useAppStore as any).mockReturnValue({
      user: mockUser,
    });

    render(<Profile />);

    expect(screen.getByText(/Last login:/)).toBeInTheDocument();
  });

  it("should not display last login when not available", () => {
    const userWithoutLastLogin = { ...mockUser, last_login: undefined };
    
    (useAppStore as any).mockReturnValue({
      user: userWithoutLastLogin,
    });

    render(<Profile />);

    expect(screen.queryByText(/Last login:/)).not.toBeInTheDocument();
  });

  it("should display account status section", () => {
    (useAppStore as any).mockReturnValue({
      user: mockUser,
    });

    render(<Profile />);

    // Check for the heading, which should be unique
    expect(screen.getByRole("heading", { name: "Account Status" })).toBeInTheDocument();
    expect(screen.getByText("Email Verified")).toBeInTheDocument();
  });

  it("should show active status for active user", () => {
    (useAppStore as any).mockReturnValue({
      user: mockUser,
    });

    render(<Profile />);

    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("should show inactive status for inactive user", () => {
    const inactiveUser = { ...mockUser, is_active: false };
    
    (useAppStore as any).mockReturnValue({
      user: inactiveUser,
    });

    render(<Profile />);

    expect(screen.getByText("Inactive")).toBeInTheDocument();
  });

  it("should show verified status for verified user", () => {
    (useAppStore as any).mockReturnValue({
      user: mockUser,
    });

    render(<Profile />);

    expect(screen.getByText("Verified")).toBeInTheDocument();
  });

  it("should show pending status for unverified user", () => {
    const unverifiedUser = { ...mockUser, is_verified: false };
    
    (useAppStore as any).mockReturnValue({
      user: unverifiedUser,
    });

    render(<Profile />);

    expect(screen.getByText("Pending")).toBeInTheDocument();
  });

  it("should display quick actions section", () => {
    (useAppStore as any).mockReturnValue({
      user: mockUser,
    });

    render(<Profile />);

    expect(screen.getByText("Quick Actions")).toBeInTheDocument();
    expect(screen.getByText("Change Password")).toBeInTheDocument();
    expect(screen.getByText("Manage API Keys")).toBeInTheDocument();
    expect(screen.getByText("Download Data")).toBeInTheDocument();
  });

  it("should display authentication system note", () => {
    (useAppStore as any).mockReturnValue({
      user: mockUser,
    });

    render(<Profile />);

    expect(screen.getByText("🚀 Authentication System Implemented")).toBeInTheDocument();
    expect(screen.getByText(/The authentication system has been successfully integrated/)).toBeInTheDocument();
  });

  it("should render user avatar icon", () => {
    (useAppStore as any).mockReturnValue({
      user: mockUser,
    });

    render(<Profile />);

    // Check that avatar circle with user icon exists
    const avatarContainer = document.querySelector('.bg-indigo-600');
    expect(avatarContainer).toBeInTheDocument();
  });

  it("should render with proper heading structure", () => {
    (useAppStore as any).mockReturnValue({
      user: mockUser,
    });

    render(<Profile />);

    expect(screen.getByRole("heading", { level: 1, name: "User Profile" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Test User" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: "Account Status" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: "Quick Actions" })).toBeInTheDocument();
  });

  it("should have clickable quick action buttons", () => {
    (useAppStore as any).mockReturnValue({
      user: mockUser,
    });

    render(<Profile />);

    const changePasswordButton = screen.getByText("Change Password");
    const manageApiKeysButton = screen.getByText("Manage API Keys");
    const downloadDataButton = screen.getByText("Download Data");

    expect(changePasswordButton.closest("button")).toBeInTheDocument();
    expect(manageApiKeysButton.closest("button")).toBeInTheDocument();
    expect(downloadDataButton.closest("button")).toBeInTheDocument();
  });
});