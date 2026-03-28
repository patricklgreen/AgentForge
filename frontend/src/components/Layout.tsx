import React from "react";
import { Link, useLocation } from "react-router-dom";
import {
  Bot,
  LayoutDashboard,
  PlusCircle,
  Github,
} from "lucide-react";
import { clsx } from "clsx";

interface LayoutProps {
  children: React.ReactNode;
}

const navItems = [
  { to: "/",              icon: LayoutDashboard, label: "Dashboard"   },
  { to: "/projects/new",  icon: PlusCircle,      label: "New Project" },
];

export function Layout({ children }: LayoutProps) {
  const location = useLocation();

  return (
    
      {/* ── Sidebar ──────────────────────────────────────────────────────────── */}
      
        {/* Logo */}
        
          
          
            AgentForge
          
        

        {/* Navigation */}
        
          {navItems.map(({ to, icon: Icon, label }) => {
            const isActive = location.pathname === to;
            return (
              
                
                {label}
              
            );
          })}
        

        {/* Footer */}
        
          
            
            Connected to AWS Bedrock
          
          
            
            View on GitHub
          
        
      

      {/* ── Main Content ─────────────────────────────────────────────────────── */}
      
        {children}
      
    
  );
}
