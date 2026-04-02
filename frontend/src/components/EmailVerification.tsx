import { useState, useEffect } from 'react';
import { CheckCircle, Clock, AlertCircle, Send } from 'lucide-react';

import { emailVerificationApi } from '../api/client';

interface EmailVerificationProps {
  user: {
    email: string;
    is_verified: boolean;
  };
}

export function EmailVerification({ user }: EmailVerificationProps) {
  const [verificationStatus, setVerificationStatus] = useState({
    is_verified: user.is_verified,
    has_pending_verification: false,
  });
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error' | 'info'; text: string } | null>(null);
  const [lastSentAt, setLastSentAt] = useState<Date | null>(null);

  // Fetch current verification status
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const status = await emailVerificationApi.getVerificationStatus();
        setVerificationStatus(status);
      } catch (error) {
        console.error('Failed to fetch verification status:', error);
      }
    };

    if (!user.is_verified) {
      fetchStatus();
    }
  }, [user.is_verified]);

  const handleSendVerification = async () => {
    // Rate limiting: prevent sending too frequently
    if (lastSentAt && Date.now() - lastSentAt.getTime() < 60000) {
      setMessage({
        type: 'error',
        text: 'Please wait at least 1 minute before requesting another verification email.'
      });
      return;
    }

    setIsLoading(true);
    setMessage(null);

    try {
      const response = await emailVerificationApi.sendVerificationEmail(user.email);
      
      if (response.success) {
        setLastSentAt(new Date());
        setMessage({
          type: 'success',
          text: 'Verification email sent! Please check your inbox and click the verification link.'
        });

        // Update status to show pending verification
        setVerificationStatus(prev => ({
          ...prev,
          has_pending_verification: true
        }));
      } else {
        setMessage({
          type: 'error',
          text: 'Failed to send verification email. Please try again.'
        });
      }
    } catch (error: any) {
      setMessage({
        type: 'error',
        text: error.response?.data?.detail || 'Failed to send verification email. Please try again.'
      });
    } finally {
      setIsLoading(false);
    }
  };

  const getTimeUntilNextSend = () => {
    if (!lastSentAt) return 0;
    const elapsed = Date.now() - lastSentAt.getTime();
    const remaining = Math.max(0, 60000 - elapsed);
    return Math.ceil(remaining / 1000);
  };

  const [countdown, setCountdown] = useState(getTimeUntilNextSend());

  useEffect(() => {
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [countdown]);

  useEffect(() => {
    setCountdown(getTimeUntilNextSend());
  }, [lastSentAt]);

  if (verificationStatus.is_verified) {
    return (
      <div className="flex items-center justify-between p-4 bg-green-50 border border-green-200 rounded-lg">
        <div className="flex items-center space-x-3">
          <CheckCircle className="h-5 w-5 text-green-500" />
          <div>
            <p className="text-green-800 font-medium">Email Verified</p>
            <p className="text-green-600 text-sm">Your email address has been verified successfully.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Status Display */}
      <div className="flex items-center justify-between p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
        <div className="flex items-center space-x-3">
          <AlertCircle className="h-5 w-5 text-yellow-500" />
          <div>
            <p className="text-yellow-800 font-medium">Email Not Verified</p>
            <p className="text-yellow-600 text-sm">
              {verificationStatus.has_pending_verification
                ? 'Verification email sent. Check your inbox and click the verification link.'
                : 'Please verify your email address to access all features.'}
            </p>
          </div>
        </div>
        
        {verificationStatus.has_pending_verification && (
          <Clock className="h-5 w-5 text-yellow-500" />
        )}
      </div>

      {/* Action Button */}
      <div className="flex items-center justify-between">
        <button
          onClick={handleSendVerification}
          disabled={isLoading || countdown > 0}
          className={`inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white transition-colors ${
            isLoading || countdown > 0
              ? 'bg-gray-400 cursor-not-allowed'
              : 'bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500'
          }`}
        >
          {isLoading ? (
            <>
              <div className="animate-spin -ml-1 mr-2 h-4 w-4 border-2 border-white border-t-transparent rounded-full"></div>
              Sending...
            </>
          ) : countdown > 0 ? (
            <>
              <Clock className="h-4 w-4 mr-2" />
              Wait {countdown}s
            </>
          ) : (
            <>
              <Send className="h-4 w-4 mr-2" />
              {verificationStatus.has_pending_verification ? 'Resend' : 'Send'} Verification Email
            </>
          )}
        </button>
      </div>

      {/* Message Display */}
      {message && (
        <div className={`p-3 rounded-md ${
          message.type === 'success' ? 'bg-green-50 text-green-800 border border-green-200' :
          message.type === 'error' ? 'bg-red-50 text-red-800 border border-red-200' :
          'bg-blue-50 text-blue-800 border border-blue-200'
        }`}>
          <p className="text-sm">{message.text}</p>
        </div>
      )}

      {/* Help Text */}
      <div className="text-xs text-gray-500 space-y-1">
        <p>• Check your spam folder if you don't see the email</p>
        <p>• Verification links expire after 24 hours</p>
        <p>• Contact support if you continue having issues</p>
      </div>
    </div>
  );
}