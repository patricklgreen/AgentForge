import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { CheckCircle, XCircle, Loader2, ArrowRight } from 'lucide-react';
import { emailVerificationApi } from '../api/client';
import { useAppStore } from '../store';

export function EmailVerificationPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { user, refreshUser } = useAppStore();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('');

  const token = searchParams.get('token');

  useEffect(() => {
    const verifyEmail = async () => {
      if (!token) {
        setStatus('error');
        setMessage('No verification token provided. Please check your email link.');
        return;
      }

      try {
        const response = await emailVerificationApi.confirmEmailVerification(token);
        
        if (response.is_verified) {
          setStatus('success');
          setMessage('Your email has been verified successfully!');
          
          // Refresh user data to update verification status
          if (refreshUser) {
            await refreshUser();
          }
        } else {
          setStatus('error');
          setMessage('Email verification failed. Please try again.');
        }
      } catch (error: any) {
        setStatus('error');
        const errorMessage = error.response?.data?.detail || 'Verification failed. The token may be invalid or expired.';
        setMessage(errorMessage);
      }
    };

    verifyEmail();
  }, [token, refreshUser]);

  const handleContinue = () => {
    if (status === 'success') {
      navigate('/profile');
    } else {
      navigate('/');
    }
  };

  const handleResendVerification = () => {
    navigate('/profile?tab=verification');
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-gray-900">Email Verification</h2>
          <p className="mt-2 text-gray-600">
            {status === 'loading' ? 'Verifying your email address...' : ''}
          </p>
        </div>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-white py-8 px-4 shadow sm:rounded-lg sm:px-10">
          <div className="text-center">
            {status === 'loading' && (
              <div className="space-y-4">
                <Loader2 className="h-12 w-12 text-indigo-600 animate-spin mx-auto" />
                <p className="text-gray-600">Please wait while we verify your email address...</p>
              </div>
            )}

            {status === 'success' && (
              <div className="space-y-4">
                <CheckCircle className="h-12 w-12 text-green-500 mx-auto" />
                <div className="space-y-2">
                  <h3 className="text-lg font-medium text-gray-900">Verification Successful!</h3>
                  <p className="text-gray-600">{message}</p>
                  {user?.email && (
                    <p className="text-sm text-gray-500">
                      Email address <span className="font-medium">{user.email}</span> is now verified.
                    </p>
                  )}
                </div>
              </div>
            )}

            {status === 'error' && (
              <div className="space-y-4">
                <XCircle className="h-12 w-12 text-red-500 mx-auto" />
                <div className="space-y-2">
                  <h3 className="text-lg font-medium text-gray-900">Verification Failed</h3>
                  <p className="text-gray-600">{message}</p>
                </div>
              </div>
            )}
          </div>

          <div className="mt-8 space-y-3">
            <button
              onClick={handleContinue}
              className="w-full flex justify-center items-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition-colors"
            >
              {status === 'success' ? (
                <>
                  Go to Profile <ArrowRight className="ml-2 h-4 w-4" />
                </>
              ) : (
                'Back to Home'
              )}
            </button>

            {status === 'error' && (
              <button
                onClick={handleResendVerification}
                className="w-full flex justify-center py-2 px-4 border border-gray-300 rounded-md shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition-colors"
              >
                Resend Verification Email
              </button>
            )}
          </div>
        </div>

        {/* Help Section */}
        <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="text-center">
            <h4 className="text-sm font-medium text-blue-800 mb-2">Need Help?</h4>
            <div className="text-xs text-blue-700 space-y-1">
              <p>• Verification links expire after 24 hours</p>
              <p>• Make sure you clicked the complete link from your email</p>
              <p>• Check your spam folder for the verification email</p>
              <p>• Contact support if you continue having issues</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}