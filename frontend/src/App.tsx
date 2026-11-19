/**
 * App 组件 - 全局 Providers（Week 3 Day 3）
 *
 * 包装：
 * - AuthProvider（全局认证状态）
 * - ErrorBoundary（顶层错误捕获）
 * - Toaster（全局通知）
 */
import type { ReactNode } from "react";
import { Toaster } from "sonner";

import { AuthProvider } from "./contexts/AuthContext";
import { ErrorBoundary } from "./components/ErrorBoundary";

export function App({ children }: { children: ReactNode }) {
  return (
    <ErrorBoundary>
      <AuthProvider>
        {children}
        <Toaster position="top-right" richColors closeButton />
      </AuthProvider>
    </ErrorBoundary>
  );
}