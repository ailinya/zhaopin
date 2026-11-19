/**
 * AuthGuard - 路由保护（Week 3 Day 1）
 *
 * 保护 HR 端路由：未登录跳 /login。
 * 已登录直接渲染 children。
 */
import { Navigate, useLocation } from "react-router";
import { type ReactNode } from "react";

import { useAuth } from "@/contexts/AuthContext";
import { Spinner } from "@/components/ui/Spinner";

interface AuthGuardProps {
  children: ReactNode;
}

export function AuthGuard({ children }: AuthGuardProps) {
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!isAuthenticated) {
    // 把当前路径作为 redirect 参数，登录后跳回
    return <Navigate to={`/login?redirect=${encodeURIComponent(location.pathname)}`} replace />;
  }

  return <>{children}</>;
}