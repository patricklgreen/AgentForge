import { useEffect, useState } from 'react';
import { useAppStore } from '../store';
import { useSearchParams } from 'react-router-dom';
import { User, Mail, Calendar, Shield } from 'lucide-react';
import { EmailVerification } from '../components/EmailVerification';

export function Profile() {
  const { user } = useAppStore();
  const [searchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState('profile');

  useEffect(() => {
    const tab = searchParams.get('tab');
    if (tab) {
      setActiveTab(tab);
    }
  }, [searchParams]);

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-600">Loading user profile...</p>
        </div>
      </div>
    );
  }

  const roleColors = {
    admin: 'bg-red-100 text-red-800',
    user: 'bg-blue-100 text-blue-800',
    viewer: 'bg-gray-100 text-gray-800',
  };

  const tabs = [
    { id: 'profile', name: 'Profile', count: null },
    { id: 'verification', name: 'Email Verification', count: user.is_verified ? null : '!' },
  ];

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="bg-white shadow rounded-lg">
          <div className="px-6 py-4 border-b border-gray-200">
            <h1 className="text-2xl font-bold text-gray-900">User Profile</h1>
          </div>
          
          {/* Tab Navigation */}
          <div className="border-b border-gray-200">
            <nav className="flex space-x-8 px-6" aria-label="Tabs">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`${
                    activeTab === tab.id
                      ? 'border-indigo-500 text-indigo-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center space-x-2`}
                >
                  <span>{tab.name}</span>
                  {tab.count && (
                    <span className={`inline-flex items-center justify-center w-4 h-4 text-xs rounded-full ${
                      tab.count === '!' ? 'bg-red-100 text-red-600' : 'bg-gray-100 text-gray-600'
                    }`}>
                      {tab.count}
                    </span>
                  )}
                </button>
              ))}
            </nav>
          </div>

          <div className="p-6">
            {activeTab === 'profile' && (
              <ProfileTab user={user} roleColors={roleColors} />
            )}
            
            {activeTab === 'verification' && (
              <EmailVerificationTab user={user} />
            )}
          </div>
        </div>
        
        {/* Development Note */}
        <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex">
            <div className="ml-3">
              <h3 className="text-sm font-medium text-blue-800">
                🚀 Authentication System Implemented
              </h3>
              <div className="mt-2 text-sm text-blue-700">
                <p>
                  The authentication system has been successfully integrated! All API endpoints are now protected,
                  and users can only access their own projects. Password changes, API key management, and other
                  advanced features can be implemented as needed.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Profile Tab Component
function ProfileTab({ user, roleColors }: { user: any; roleColors: any }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* Profile Information */}
      <div className="space-y-6">
        <div className="flex items-center space-x-4">
          <div className="h-20 w-20 bg-indigo-600 rounded-full flex items-center justify-center">
            <User className="h-10 w-10 text-white" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-gray-900">
              {user.full_name || user.username}
            </h2>
            <p className="text-gray-600">@{user.username}</p>
          </div>
        </div>

        <div className="space-y-4">
          <div className="flex items-center space-x-3">
            <Mail className="h-5 w-5 text-gray-400" />
            <span className="text-gray-900">{user.email}</span>
          </div>
          
          <div className="flex items-center space-x-3">
            <Shield className="h-5 w-5 text-gray-400" />
            <span className={`px-2 py-1 rounded-full text-xs font-medium ${roleColors[user.role]}`}>
              {user.role.charAt(0).toUpperCase() + user.role.slice(1)}
            </span>
          </div>
          
          <div className="flex items-center space-x-3">
            <Calendar className="h-5 w-5 text-gray-400" />
            <span className="text-gray-900">
              Member since {new Date(user.created_at).toLocaleDateString()}
            </span>
          </div>
          
          {user.last_login && (
            <div className="flex items-center space-x-3">
              <Calendar className="h-5 w-5 text-gray-400" />
              <span className="text-gray-900">
                Last login: {new Date(user.last_login).toLocaleString()}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Account Status */}
      <div className="space-y-6">
        <div>
          <h3 className="text-lg font-medium text-gray-900 mb-4">Account Status</h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-gray-600">Account Status</span>
              <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                user.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
              }`}>
                {user.is_active ? 'Active' : 'Inactive'}
              </span>
            </div>
            
            <div className="flex items-center justify-between">
              <span className="text-gray-600">Email Verified</span>
              <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                user.is_verified ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
              }`}>
                {user.is_verified ? 'Verified' : 'Pending'}
              </span>
            </div>
          </div>
        </div>

        {/* Quick Actions */}
        <div>
          <h3 className="text-lg font-medium text-gray-900 mb-4">Quick Actions</h3>
          <div className="space-y-2">
            <button className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-md transition-colors">
              Change Password
            </button>
            <button className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-md transition-colors">
              Manage API Keys
            </button>
            <button className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 rounded-md transition-colors">
              Download Data
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// Email Verification Tab Component
function EmailVerificationTab({ user }: { user: any }) {
  return (
    <div className="max-w-2xl">
      <div className="mb-6">
        <h3 className="text-lg font-medium text-gray-900 mb-2">Email Verification</h3>
        <p className="text-gray-600">
          Verify your email address to access all features and improve account security.
        </p>
      </div>
      
      <EmailVerification 
        user={{
          email: user.email,
          is_verified: user.is_verified
        }}
      />
    </div>
  );
}