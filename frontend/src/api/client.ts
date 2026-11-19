/**
 * API 客户端（§14.10 + §16.4 借鉴 GraphRAGAgent）
 *
 * 特性：
 * - axios 实例（拦截器自动加 JWT）
 * - ApiError class（code 区分错误类型）
 * - 401 自动 refresh + 重试
 * - 统一错误处理（前端 §15.9 用）
 */
import axios, { AxiosInstance, isAxiosError } from "axios";

import { authStorage } from "@/lib/auth";

// ===== ApiError class（§16.4 借鉴）=====
export class ApiError extends Error {
  code: number;
  data: any;

  constructor(code: number, msg: string, data: any = null) {
    super(msg);
    this.name = "ApiError";
    this.code = code;
    this.data = data;
  }

  /** 是否可重试的错误（如 401 token 过期）*/
  get isRetryable(): boolean {
    return this.code === 4001 || this.code === 4002;  // UNAUTHORIZED / TOKEN_EXPIRED
  }
}

// ===== axios 实例 =====

export const apiClient: AxiosInstance = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "",
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

// ===== 请求拦截器：自动加 JWT =====
apiClient.interceptors.request.use((config) => {
  const auth = authStorage.get();
  if (auth?.access_token) {
    config.headers.Authorization = `Bearer ${auth.access_token}`;
  }
  return config;
});

// ===== 响应拦截器：401 自动 refresh + ApiError 包装 =====
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;

    // 401 + 未重试过 + 有 refresh token → 尝试刷新
    if (
      error.response?.status === 401 &&
      !original._retry &&
      !original.url?.includes("/api/auth/")
    ) {
      original._retry = true;
      const auth = authStorage.get();
      if (auth?.refresh_token) {
        try {
          const resp = await axios.post(
            "/api/auth/refresh",
            null,
            { params: { refresh_token: auth.refresh_token } }
          );
          // 后端响应也是 APIResponse 格式
          const newAuth = resp.data.data;
          authStorage.set(newAuth);
          original.headers.Authorization = `Bearer ${newAuth.access_token}`;
          return apiClient(original);  // 重试原请求
        } catch {
          // refresh 失败，清空登录态跳登录页
          authStorage.clear();
          if (typeof window !== "undefined") {
            window.location.href = "/login";
          }
        }
      }
    }

    // 把后端的 APIResponse.err 转为 ApiError
    if (isAxiosError(error) && error.response?.data) {
      const data = error.response.data;
      if (typeof data.code === "number" && data.code !== 0) {
        throw new ApiError(data.code, data.msg || "请求失败", data.data);
      }
    }

    // 其他错误（网络错误等）
    return Promise.reject(error);
  }
);

// ===== 工具函数 =====

/**
 * 检查错误是否为 ApiError
 */
export function isApiError(err: unknown): err is ApiError {
  return err instanceof ApiError;
}