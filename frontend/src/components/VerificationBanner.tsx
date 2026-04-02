import { useState } from 'react';
import { AlertCircle, X, Mail } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface VerificationBannerProps {
  user: {
    email: string;
    is_verified: boolean;
  };
}

export function VerificationBanner({ user }: VerificationBannerProps) {
  const [isDismissed, setIsDismissed] = useState(false);
  const navigate = useNavigate();

  // Don't show banner if user is verified or has dismissed it
  if (user.is_verified || isDismissed) {
    return null;
  }

  const handleVerifyClick = () => {
    navigate('/profile?tab=verification');
  };

  return (
    <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-6">
      <div className="flex">
        <div className="flex-shrink-0">
          <AlertCircle className="h-5 w-5 text-yellow-400" />
        </div>
        <div className="ml-3 flex-1">
          <p className="text-sm text-yellow-700">
            <span className="font-medium">Email verification required.</span>
            {' '}Please verify your email address ({user.email}) to access all features.
          </p>
          <div className="mt-2">
            <button
              onClick={handleVerifyClick}
              className="inline-flex items-center text-sm text-yellow-800 underline hover:text-yellow-900"
            >
              <Mail className="h-4 w-4 mr-1" />
              Verify email address
            </button>
          </div>
        </div>
        <div className="ml-auto pl-3">
          <div className="-mx-1.5 -my-1.5">
            <button
              onClick={() => setIsDismissed(true)}
              className="inline-flex bg-yellow-50 rounded-md p-1.5 text-yellow-500 hover:bg-yellow-100 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-yellow-50 focus:ring-yellow-600"
            >
              <span className="sr-only">Dismiss</span>
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}