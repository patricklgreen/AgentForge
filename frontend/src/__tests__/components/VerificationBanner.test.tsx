/**
 * Tests for VerificationBanner Component
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { VerificationBanner } from '../../components/VerificationBanner'

const mockUser = {
  email: 'test@example.com',
  is_verified: false,
}

const renderWithRouter = (component: React.ReactElement) => {
  return render(
    <BrowserRouter>
      {component}
    </BrowserRouter>
  )
}

describe('VerificationBanner', () => {
  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear()
  })

  it('should render verification warning banner', () => {
    renderWithRouter(<VerificationBanner user={mockUser} />)

    expect(screen.getByText(/email verification required/i)).toBeInTheDocument()
    expect(screen.getByText(/verify email address/i)).toBeInTheDocument()
  })

  it('should have button to navigate to profile verification tab', () => {
    renderWithRouter(<VerificationBanner user={mockUser} />)

    const verifyButton = screen.getByText(/verify email address/i)
    expect(verifyButton).toBeInTheDocument()
    expect(verifyButton.tagName).toBe('BUTTON')
  })

  it('should be dismissible', () => {
    renderWithRouter(<VerificationBanner user={mockUser} />)

    const dismissButton = screen.getByRole('button', { name: /dismiss/i })
    expect(dismissButton).toBeInTheDocument()

    fireEvent.click(dismissButton)

    expect(screen.queryByText(/email verification required/i)).not.toBeInTheDocument()
  })

  it('should remember dismissal in localStorage', () => {
    renderWithRouter(<VerificationBanner user={mockUser} />)

    const dismissButton = screen.getByRole('button', { name: /dismiss/i })
    fireEvent.click(dismissButton)

    expect(localStorage.getItem('verificationBannerDismissed')).toBe('true')
  })

  it('should not render when previously dismissed', () => {
    localStorage.setItem('verificationBannerDismissed', 'true')

    renderWithRouter(<VerificationBanner user={mockUser} />)

    expect(screen.queryByText(/email verification required/i)).not.toBeInTheDocument()
  })

  it('should show after localStorage is cleared', () => {
    localStorage.setItem('verificationBannerDismissed', 'true')

    renderWithRouter(<VerificationBanner user={mockUser} />)
    expect(screen.queryByText(/email verification required/i)).not.toBeInTheDocument()

    // Clear localStorage and re-render
    localStorage.clear()
    
    renderWithRouter(<VerificationBanner user={mockUser} />)
    expect(screen.getByText(/email verification required/i)).toBeInTheDocument()
  })

  it('should have proper warning styling', () => {
    renderWithRouter(<VerificationBanner user={mockUser} />)

    const banner = screen.getByText(/email verification required/i).closest('[class*="bg-yellow-50"]')
    expect(banner).toHaveClass('bg-yellow-50')
    expect(banner).toHaveClass('border-yellow-400')
  })

  it('should have accessible dismiss button', () => {
    renderWithRouter(<VerificationBanner user={mockUser} />)

    const dismissButton = screen.getByRole('button', { name: /dismiss/i })
    expect(dismissButton).toHaveAttribute('aria-label', 'Dismiss banner')
  })
})