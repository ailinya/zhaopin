/**
 * LoginPage - 登录表单
 * @author 星浩AI
 */
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";
import { LogIn } from "lucide-react";

import { apiClient, ApiError } from "@/api/client";
import { useAuth } from "@/contexts/AuthContext";
import { Button, Input, Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui";

interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: {
    id: string;
    username: string;
    email: string;
    full_name: string | null;
  };
}

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [isLoading, setIsLoading] = useState(false);

  // 预设用户名密码（本地开发用）
  const DEFAULT_USERNAME = "admin";
  const DEFAULT_PASSWORD = "123456";

  const [formData, setFormData] = useState({
    username: DEFAULT_USERNAME,
    password: DEFAULT_PASSWORD,
  });

  const redirect = searchParams.get("redirect") || "/dashboard";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.username || !formData.password) {
      toast.error("请输入用户名和密码");
      return;
    }

    setIsLoading(true);
    try {
      const res = await apiClient.post<{ data: LoginResponse }>("/api/auth/login", {
        username: formData.username,
        password: formData.password,
      });
      login(res.data.data);
      toast.success(`欢迎回来，${res.data.data.user.username}`);
      navigate(redirect, { replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === 4004 || err.code === 4001) {
          toast.error("用户名或密码错误");
        } else {
          toast.error(err.message || "登录失败");
        }
      } else {
        toast.error("网络错误，请重试");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-screen items-center justify-center bg-muted/30">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          {/* 星浩AI Logo */}
          <div className="mx-auto mb-4">
            <img src="/logo.jpg" alt="星浩AI" className="h-16 w-auto rounded-lg" />
          </div>
          <CardTitle className="text-2xl">星浩AI · 智能面试系统</CardTitle>
          <CardDescription>AI 驱动的自动化招聘解决方案</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="username" className="text-sm font-medium">
                用户名
              </label>
              <Input
                id="username"
                type="text"
                placeholder="admin"
                autoComplete="username"
                value={formData.username}
                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="password" className="text-sm font-medium">
                密码
              </label>
              <Input
                id="password"
                type="password"
                placeholder="••••••"
                autoComplete="current-password"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              />
            </div>

            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? "登录中..." : "登录"}
            </Button>
          </form>

          <p className="text-xs text-center text-muted-foreground mt-6">
            v1.0 · 由 <span className="font-medium">星浩AI</span> 驱动
          </p>
          <p className="text-xs text-center text-muted-foreground mt-2">
            扫码关注公众号「星浩AI」
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
