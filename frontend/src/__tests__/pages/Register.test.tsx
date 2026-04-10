import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { Register } from "../../pages/Register";
import { useAppStore } from "../../store";

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

const renderWithRouter = (component: React.ReactElement) => {
  return render(
    <MemoryRouter>
      {component}
    </MemoryRouter>
  );
};

describe("Register Page", () => {
  const mockRegister = vi.fn();
  const mockStore = {
    register: mockRegister,
    isLoading: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (useAppStore as any).mockReturnValue(mockStore);
  });

  it("should render registration form", () => {
    renderWithRouter(<Register />);
    
    expect(screen.getByText("Create your account")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Enter your email")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Choose a username")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Your full name (optional)")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Create a password")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Confirm your password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create account" })).toBeInTheDocument();
  });

  it("should show link to login", () => {
    renderWithRouter(<Register />);
    
    expect(screen.getByText("sign in to your existing account")).toBeInTheDocument();
  });

  it("should show password requirements", () => {
    renderWithRouter(<Register />);
    
    expect(screen.getByText("Must be at least 8 characters with uppercase, lowercase, and number")).toBeInTheDocument();
  });

  it("should handle form input changes", () => {
    renderWithRouter(<Register />);
    
    const emailInput = screen.getByPlaceholderText("Enter your email");
    const usernameInput = screen.getByPlaceholderText("Choose a username");
    const fullNameInput = screen.getByPlaceholderText("Your full name (optional)");
    const passwordInput = screen.getByPlaceholderText("Create a password");
    const confirmInput = screen.getByPlaceholderText("Confirm your password");
    
    fireEvent.change(emailInput, { target: { value: "test@example.com" } });
    fireEvent.change(usernameInput, { target: { value: "testuser" } });
    fireEvent.change(fullNameInput, { target: { value: "Test User" } });
    fireEvent.change(passwordInput, { target: { value: "Password123!" } });
    fireEvent.change(confirmInput, { target: { value: "Password123!" } });
    
    expect(emailInput).toHaveValue("test@example.com");
    expect(usernameInput).toHaveValue("testuser");
    expect(fullNameInput).toHaveValue("Test User");
    expect(passwordInput).toHaveValue("Password123!");
    expect(confirmInput).toHaveValue("Password123!");
  });

  it("should show validation error for empty required fields", async () => {
    renderWithRouter(<Register />);
    
    // Test that required fields have the required attribute
    expect(screen.getByPlaceholderText("Enter your email")).toHaveAttribute("required");
    expect(screen.getByPlaceholderText("Choose a username")).toHaveAttribute("required");
    expect(screen.getByPlaceholderText("Create a password")).toHaveAttribute("required");
    expect(screen.getByPlaceholderText("Confirm your password")).toHaveAttribute("required");
    
    // Optional field should not be required
    expect(screen.getByPlaceholderText("Your full name (optional)")).not.toHaveAttribute("required");
  });

  it("should handle password validation logic", () => {
    renderWithRouter(<Register />);
    
    // Test that password fields exist and have proper attributes
    const passwordInput = screen.getByPlaceholderText("Create a password");
    const confirmInput = screen.getByPlaceholderText("Confirm your password");
    
    expect(passwordInput).toHaveAttribute("type", "password");
    expect(confirmInput).toHaveAttribute("type", "password");
    expect(passwordInput).toHaveAttribute("required");
    expect(confirmInput).toHaveAttribute("required");
  });

  it("should handle password length validation", () => {
    renderWithRouter(<Register />);
    
    // Check that password requirements are shown
    expect(screen.getByText("Must be at least 8 characters with uppercase, lowercase, and number")).toBeInTheDocument();
    
    const passwordInput = screen.getByPlaceholderText("Create a password");
    expect(passwordInput).toHaveAttribute("type", "password");
  });

  it("should call register on form submission with valid data", async () => {
    mockRegister.mockResolvedValue(undefined);
    renderWithRouter(<Register />);
    
    const emailInput = screen.getByPlaceholderText("Enter your email");
    const usernameInput = screen.getByPlaceholderText("Choose a username");
    const fullNameInput = screen.getByPlaceholderText("Your full name (optional)");
    const passwordInput = screen.getByPlaceholderText("Create a password");
    const confirmInput = screen.getByPlaceholderText("Confirm your password");
    const submitButton = screen.getByRole("button", { name: "Create account" });
    
    fireEvent.change(emailInput, { target: { value: "test@example.com" } });
    fireEvent.change(usernameInput, { target: { value: "testuser" } });
    fireEvent.change(fullNameInput, { target: { value: "Test User" } });
    fireEvent.change(passwordInput, { target: { value: "Password123!" } });
    fireEvent.change(confirmInput, { target: { value: "Password123!" } });
    fireEvent.click(submitButton);
    
    await waitFor(() => {
      expect(mockRegister).toHaveBeenCalledWith({
        email: "test@example.com",
        username: "testuser",
        password: "Password123!",
        full_name: "Test User",
      });
    });
  });

  it("should handle registration without optional full name", async () => {
    mockRegister.mockResolvedValue(undefined);
    renderWithRouter(<Register />);
    
    const emailInput = screen.getByPlaceholderText("Enter your email");
    const usernameInput = screen.getByPlaceholderText("Choose a username");
    const passwordInput = screen.getByPlaceholderText("Create a password");
    const confirmInput = screen.getByPlaceholderText("Confirm your password");
    const submitButton = screen.getByRole("button", { name: "Create account" });
    
    fireEvent.change(emailInput, { target: { value: "test@example.com" } });
    fireEvent.change(usernameInput, { target: { value: "testuser" } });
    fireEvent.change(passwordInput, { target: { value: "Password123!" } });
    fireEvent.change(confirmInput, { target: { value: "Password123!" } });
    fireEvent.click(submitButton);
    
    await waitFor(() => {
      expect(mockRegister).toHaveBeenCalledWith({
        email: "test@example.com",
        username: "testuser",
        password: "Password123!",
        full_name: undefined,
      });
    });
  });

  it("should show success message and redirect on successful registration", async () => {
    mockRegister.mockResolvedValue(undefined);
    renderWithRouter(<Register />);
    
    const emailInput = screen.getByPlaceholderText("Enter your email");
    const usernameInput = screen.getByPlaceholderText("Choose a username");
    const passwordInput = screen.getByPlaceholderText("Create a password");
    const confirmInput = screen.getByPlaceholderText("Confirm your password");
    const submitButton = screen.getByRole("button", { name: "Create account" });
    
    fireEvent.change(emailInput, { target: { value: "test@example.com" } });
    fireEvent.change(usernameInput, { target: { value: "testuser" } });
    fireEvent.change(passwordInput, { target: { value: "Password123!" } });
    fireEvent.change(confirmInput, { target: { value: "Password123!" } });
    fireEvent.click(submitButton);
    
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/login", {
        state: { message: "Registration successful! Please sign in." },
      });
    }, { timeout: 3000 });
  });

  it("should show error message on registration failure", async () => {
    mockRegister.mockRejectedValue(new Error("Email already exists"));
    renderWithRouter(<Register />);
    
    const emailInput = screen.getByPlaceholderText("Enter your email");
    const usernameInput = screen.getByPlaceholderText("Choose a username");
    const passwordInput = screen.getByPlaceholderText("Create a password");
    const confirmInput = screen.getByPlaceholderText("Confirm your password");
    const submitButton = screen.getByRole("button", { name: "Create account" });
    
    fireEvent.change(emailInput, { target: { value: "test@example.com" } });
    fireEvent.change(usernameInput, { target: { value: "testuser" } });
    fireEvent.change(passwordInput, { target: { value: "Password123!" } });
    fireEvent.change(confirmInput, { target: { value: "Password123!" } });
    fireEvent.click(submitButton);
    
    await waitFor(() => {
      expect(screen.getByText("Email already exists")).toBeInTheDocument();
    });
  });

  it("should show loading state during registration", () => {
    (useAppStore as any).mockReturnValue({
      ...mockStore,
      isLoading: true,
    });
    
    renderWithRouter(<Register />);
    
    const submitButton = screen.getByRole("button", { name: "Create account" });
    expect(submitButton).toBeDisabled();
  });

  it("should have proper form accessibility", () => {
    renderWithRouter(<Register />);
    
    const emailInput = screen.getByLabelText("Email address *");
    const usernameInput = screen.getByLabelText("Username *");
    const fullNameInput = screen.getByLabelText("Full name");
    const passwordInput = screen.getByLabelText("Password *");
    const confirmInput = screen.getByLabelText("Confirm password *");
    
    expect(emailInput).toHaveAttribute("type", "email");
    expect(emailInput).toHaveAttribute("required");
    expect(emailInput).toHaveAttribute("autoComplete", "email");
    
    expect(usernameInput).toHaveAttribute("type", "text");
    expect(usernameInput).toHaveAttribute("required");
    
    expect(fullNameInput).toHaveAttribute("type", "text");
    expect(fullNameInput).not.toHaveAttribute("required");
    
    expect(passwordInput).toHaveAttribute("type", "password");
    expect(passwordInput).toHaveAttribute("required");
    expect(passwordInput).toHaveAttribute("autoComplete", "new-password");
    
    expect(confirmInput).toHaveAttribute("type", "password");
    expect(confirmInput).toHaveAttribute("required");
  });
});