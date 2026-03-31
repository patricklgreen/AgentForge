import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { NotFound } from "../../pages/NotFound";
import { MemoryRouter } from "react-router-dom";

const renderWithRouter = (component: React.ReactElement) => {
  return render(
    <MemoryRouter>
      {component}
    </MemoryRouter>
  );
};

describe("NotFound Page", () => {
  it("should render 404 error message", () => {
    renderWithRouter(<NotFound />);
    
    expect(screen.getByText("404")).toBeInTheDocument();
    expect(screen.getByText("Page not found")).toBeInTheDocument();
  });

  it("should render descriptive error message", () => {
    renderWithRouter(<NotFound />);
    
    expect(screen.getByText(/Sorry, we couldn't find the page you're looking for/)).toBeInTheDocument();
  });

  it("should have link back to dashboard", () => {
    renderWithRouter(<NotFound />);
    
    const homeLink = screen.getByText("Go back home");
    expect(homeLink.closest("a")).toHaveAttribute("href", "/");
  });

  it("should have contact support link", () => {
    renderWithRouter(<NotFound />);
    
    expect(screen.getByText("contact support")).toBeInTheDocument();
  });

  it("should render with proper heading structure", () => {
    renderWithRouter(<NotFound />);
    
    // Check for main heading
    expect(screen.getByRole("heading", { level: 1 })).toBeInTheDocument();
  });
});