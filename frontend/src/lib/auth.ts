/**
 * 鉴权状态管理（§14.9）
 *
 * MVP 方案：JWT 存在 localStorage
 * 注意：可被 XSS 偷（XSS 风险需前端注意）
 *
 * Phase 2 可考虑：httpOnly cookie
 */
const STORAGE_KEY = "interview_auth";

export interface UserInfo {
  id: string;
  username: string;
  email: string;
  full_name: string | null;
}

export interface AuthState {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: UserInfo;
}

export const authStorage = {
  /** 获取登录态 */
  get(): AuthState | null {
    if (typeof window === "undefined") return null;
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as AuthState;
    } catch {
      return null;
    }
  },

  /** 保存登录态 */
  set(state: AuthState) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  },

  /** 更新 token（refresh 后用）*/
  updateTokens(access_token: string, refresh_token: string) {
    const current = this.get();
    if (!current) return;
    this.set({ ...current, access_token, refresh_token });
  },

  /** 清空登录态 */
  clear() {
    localStorage.removeItem(STORAGE_KEY);
  },

  /** 是否已登录 */
  isAuthenticated(): boolean {
    return this.get() !== null;
  },

  /** 获取当前用户（未登录返回 null）*/
  getCurrentUser(): UserInfo | null {
    return this.get()?.user ?? null;
  },
};