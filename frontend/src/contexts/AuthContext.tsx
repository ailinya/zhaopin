/**
 * AuthContext - 全局认证状态管理（Week 3 Day 1）
 *
 * 包装 authStorage，提供：
 * - user: 当前用户（null = 未登录）
 * - login(token): 设置登录态
 * - logout(): 清空登录态
 * - isAuthenticated: 是否已登录
 *
 * 用法：
 *   const { user, isAuthenticated, login, logout } = useAuth();
 */
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

import { authStorage, type AuthState, type UserInfo } from "@/lib/auth";

interface AuthContextValue {
  user: UserInfo | null;
  isAuthenticated: boolean;
  loading: boolean;
  login: (state: AuthState) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);

  // 初始化：从 localStorage 恢复
  useEffect(() => {
    const stored = authStorage.get();
    setUser(stored?.user ?? null);
    setLoading(false);
  }, []);

  const login = (state: AuthState) => {
    authStorage.set(state);
    setUser(state.user);
  };

  const logout = () => {
    authStorage.clear();
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: user !== null,
        loading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}