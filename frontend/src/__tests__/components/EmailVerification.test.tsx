/**
 * Tests for Email Verification Components
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { EmailVerification } from '../../components/EmailVerification'
import { EmailVerificationPage } from '../../pages/EmailVerificationPage'
import { emailVerificationApi } from '../../api/client'

const mockUser = {
  email: 'test@example.com',
  is_verified: false,
}

// Mock the API - provide direct emailVerificationApi mock 
vi.mock('../../api/client', () => ({
  emailVerificationApi: {
    sendVerificationEmail: vi.fn(),
    confirmEmailVerification: vi.fn(),
    getVerificationStatus: vi.fn(),
  }
}))

// Mock useAppStore
const mockRefreshUser = vi.fn()
vi.mock('../../store', () => ({
  useAppStore: () => ({
    user: mockUser,
    refreshUser: mockRefreshUser,
  }),
}))

// Mock useSearchParams
const mockSetSearchParams = vi.fn()
const mockSearchParams = new URLSearchParams()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useSearchParams: () => [mockSearchParams, mockSetSearchParams],
    useNavigate: () => vi.fn(),
  }
})

const renderWithRouter = (component: React.ReactElement) => {
  return render(
    <BrowserRouter>
      {component}
    </BrowserRouter>
  )
}

describe('EmailVerification Component', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should render verification status correctly', async () => {
    vi.mocked(emailVerificationApi.getVerificationStatus).mockResolvedValue({
      is_verified: false,
      email: 'test@example.com',
      has_pending_verification: false,
    })

    renderWithRouter(<EmailVerification user={mockUser} />)

    await waitFor(() => {
      expect(screen.getByText(/Email verification/)).toBeInTheDocument()
    })
  })

  it('should show verified status for verified email', async () => {
    vi.mocked(emailVerificationApi.getVerificationStatus).mockResolvedValue({
      is_verified: true,
      email: 'test@example.com',
      has_pending_verification: false,
    })

    renderWithRouter(<EmailVerification user={mockUser} />)

    await waitFor(() => {
      expect(screen.getByText(/verified/i)).toBeInTheDocument()
    })
  })

  it('should allow sending verification email', async () => {
    vi.mocked(emailVerificationApi.getVerificationStatus).mockResolvedValue({
      is_verified: false,
      email: 'test@example.com',
      has_pending_verification: false,
    })

    vi.mocked(emailVerificationApi.sendVerificationEmail).mockResolvedValue({
      success: true,
      message: 'Verification email sent',
    })

    renderWithRouter(<EmailVerification user={mockUser} />)

    await waitFor(() => {
      const sendButton = screen.getByText(/send verification email/i)
      expect(sendButton).toBeInTheDocument()
    })

    const sendButton = screen.getByText(/send verification email/i)
    fireEvent.click(sendButton)

    await waitFor(() => {
      expect(emailVerificationApi.sendVerificationEmail).toHaveBeenCalledWith('test@example.com')
    })
  })

  it('should show cooldown after sending email', async () => {
    vi.mocked(emailVerificationApi.getVerificationStatus).mockResolvedValue({
      is_verified: false,
      email: 'test@example.com',
      has_pending_verification: false,
    })

    vi.mocked(emailVerificationApi.sendVerificationEmail).mockResolvedValue({
      success: true,
      message: 'Verification email sent',
    })

    renderWithRouter(<EmailVerification user={mockUser} />)

    await waitFor(() => {
      const sendButton = screen.getByText(/send verification email/i)
      fireEvent.click(sendButton)
    })

    await waitFor(() => {
      expect(screen.getByText(/resend in/i)).toBeInTheDocument()
    })
  })

  it('should handle send email error', async () => {
    vi.mocked(emailVerificationApi.getVerificationStatus).mockResolvedValue({
      is_verified: false,
      email: 'test@example.com',
      has_pending_verification: false,
    })

    vi.mocked(emailVerificationApi.sendVerificationEmail).mockRejectedValue(
      new Error('Failed to send email')
    )

    renderWithRouter(<EmailVerification user={mockUser} />)

    await waitFor(() => {
      const sendButton = screen.getByText(/send verification email/i)
      fireEvent.click(sendButton)
    })

    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument()
    })
  })
})

describe('EmailVerificationPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should show loading initially', () => {
    // Mock URLSearchParams to return a token
    Object.defineProperty(window, 'location', {
      value: { search: '?token=test-token' },
      writable: true,
    })

    renderWithRouter(<EmailVerificationPage />)
    expect(screen.getByText(/verifying/i)).toBeInTheDocument()
  })

  it('should verify token on mount', async () => {
    Object.defineProperty(window, 'location', {
      value: { search: '?token=test-token' },
      writable: true,
    })

    vi.mocked(emailVerificationApi.confirmEmailVerification).mockResolvedValue({
      message: 'Email verified successfully',
      is_verified: true,
    })

    renderWithRouter(<EmailVerificationPage />)

    await waitFor(() => {
      expect(emailVerificationApi.confirmEmailVerification).toHaveBeenCalledWith('test-token')
    })
  })

  it('should show success message after verification', async () => {
    Object.defineProperty(window, 'location', {
      value: { search: '?token=test-token' },
      writable: true,
    })

    vi.mocked(emailVerificationApi.confirmEmailVerification).mockResolvedValue({
      message: 'Email verified successfully',
      is_verified: true,
    })

    renderWithRouter(<EmailVerificationPage />)

    await waitFor(() => {
      expect(screen.getByText(/success/i)).toBeInTheDocument()
    })

    expect(mockRefreshUser).toHaveBeenCalled()
  })

  it('should show error message for invalid token', async () => {
    Object.defineProperty(window, 'location', {
      value: { search: '?token=invalid-token' },
      writable: true,
    })

    vi.mocked(emailVerificationApi.confirmEmailVerification).mockRejectedValue(
      new Error('Invalid token')
    )

    renderWithRouter(<EmailVerificationPage />)

    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument()
    })
  })

  it('should show error when no token provided', () => {
    Object.defineProperty(window, 'location', {
      value: { search: '' },
      writable: true,
    })

    renderWithRouter(<EmailVerificationPage />)

    expect(screen.getByText(/no verification token/i)).toBeInTheDocument()
  })

  it('should have link back to profile', async () => {
    Object.defineProperty(window, 'location', {
      value: { search: '?token=test-token' },
      writable: true,
    })

    vi.mocked(emailVerificationApi.confirmEmailVerification).mockResolvedValue({
      message: 'Email verified successfully',
      is_verified: true,
    })

    renderWithRouter(<EmailVerificationPage />)

    await waitFor(() => {
      const profileLink = screen.getByText(/go to profile/i)
      expect(profileLink).toBeInTheDocument()
      expect(profileLink.closest('a')).toHaveAttribute('href', '/profile?tab=verification')
    })
  })
})