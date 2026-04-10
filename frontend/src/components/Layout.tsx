import React from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  Bot,
  LayoutDashboard,
  PlusCircle,
  Github,
  User,
  LogOut,
  Settings,
} from "lucide-react";
import { clsx } from "clsx";
import { useAppStore } from "../store";

interface LayoutProps {
  children: React.ReactNode;
}

const navItems = [
  { to: "/",              icon: LayoutDashboard, label: "Dashboard"   },
  { to: "/projects/new",  icon: PlusCircle,      label: "New Project" },
];

export function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAppStore();

  const handleLogout = async () => {
    try {
      await logout();
      navigate('/login');
    } catch (error) {
      // Still navigate to login even if logout fails
      console.error('Logout failed:', error);
      navigate('/login');
    }
  };

  // Don't show sidebar layout for auth pages
  if (location.pathname === '/login' || location.pathname === '/register') {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen bg-gray-950 flex">
      {/* Sidebar */}
      <div className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col">
        {/* Logo */}
        <div className="flex items-center gap-3 px-6 py-4 border-b border-gray-800">
          <Bot className="h-8 w-8 text-blue-400" />
          <h1 className="text-xl font-bold text-white">
            AgentForge
          </h1>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-4 py-6 space-y-2">
          {navItems.map(({ to, icon: Icon, label }) => {
            const isActive = location.pathname === to;
            return (
              <Link
                key={to}
                to={to}
                className={clsx(
                  "flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors",
                  isActive
                    ? "bg-gray-800 text-white border border-gray-700"
                    : "text-gray-300 hover:bg-gray-800 hover:text-white"
                )}
              >
                <Icon className="h-5 w-5" />
                {label}
              </Link>
            );
          })}
        </nav>

        {/* User Profile Section */}
        <div className="px-4 py-4 border-t border-gray-800 space-y-3">
          {user && (
            <div className="flex items-center gap-3 px-3 py-2 rounded-lg bg-gray-800">
              <div className="h-8 w-8 bg-indigo-600 rounded-full flex items-center justify-center">
                <User className="h-4 w-4 text-white" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-white truncate">
                  {user.full_name || user.username}
                </p>
                <p className="text-xs text-gray-400 truncate">
                  {user.email}
                </p>
              </div>
            </div>
          )}
          
          <div className="flex gap-2">
            <Link
              to="/profile"
              className="flex-1 flex items-center justify-center gap-2 px-3 py-2 text-xs text-gray-400 hover:text-gray-300 hover:bg-gray-800 rounded-lg transition-colors"
            >
              <Settings className="h-4 w-4" />
              Settings
            </Link>
            <button
              onClick={handleLogout}
              className="flex-1 flex items-center justify-center gap-2 px-3 py-2 text-xs text-gray-400 hover:text-gray-300 hover:bg-gray-800 rounded-lg transition-colors"
            >
              <LogOut className="h-4 w-4" />
              Logout
            </button>
          </div>
          
          <div className="flex items-center gap-2 text-xs text-green-400">
            <div className="h-2 w-2 bg-green-400 rounded-full"></div>
            Connected to AWS Bedrock
          </div>
          <a
            href="https://github.com/3Ci-Consulting/agentforge"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-xs text-gray-400 hover:text-gray-300"
          >
            <Github className="h-4 w-4" />
            View on GitHub
          </a>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {children}
      </div>
    </div>
  );
}