import React, { useEffect } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAppStore } from '../store';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requireRole?: 'admin' | 'user' | 'viewer';
}

export function ProtectedRoute({ children, requireRole }: ProtectedRouteProps) {
  const { isAuthenticated, user, isLoading, checkAuth } = useAppStore();
  const location = useLocation();

  useEffect(() => {
    // Always check authentication on mount and when dependencies change
    checkAuth();
  }, []); // Only run once on mount

  // Show loading spinner while checking auth
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-indigo-500"></div>
      </div>
    );
  }

  // Redirect to login if not authenticated after loading is complete
  if (!isLoading && !isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Don't render protected content until authentication is confirmed
  if (!user || !isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-indigo-500"></div>
      </div>
    );
  }

  // Check role-based access if required
  if (requireRole && user && user.role !== requireRole) {
    // For role hierarchy: admin > user > viewer
    const roleHierarchy = { admin: 3, user: 2, viewer: 1 };
    const userLevel = roleHierarchy[user.role];
    const requiredLevel = roleHierarchy[requireRole];
    
    if (userLevel < requiredLevel) {
      return (
        <div className="min-h-screen flex items-center justify-center">
          <div className="text-center">
            <h1 className="text-2xl font-bold text-gray-900 mb-4">Access Denied</h1>
            <p className="text-gray-600">You don't have permission to access this page.</p>
          </div>
        </div>
      );
    }
  }

  return <>{children}</>;
}

interface PublicOnlyRouteProps {
  children: React.ReactNode;
}

export function PublicOnlyRoute({ children }: PublicOnlyRouteProps) {
  const { isAuthenticated, isLoading } = useAppStore();

  // Show loading spinner while checking auth
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-indigo-500"></div>
      </div>
    );
  }

  // Redirect to dashboard if already authenticated
  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}