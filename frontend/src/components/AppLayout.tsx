/**
 * AppLayout - HR 端整体布局（Week 3 Day 1）
 * @author 星浩AI
 *
 * 结构：
 * ┌─────────────────────────────────────┐
 * │  Sidebar (left, 240px)  │  Main     │
 * │  - Logo                │           │
 * │  - Nav (Dashboard /    │           │
 * │    Positions / etc)    │  Outlet   │
 * │                        │           │
 * │  User info (bottom)    │           │
 * └─────────────────────────────────────┘
 */
import { NavLink, Outlet, useNavigate } from "react-router";
import { LogOut, LayoutDashboard, Briefcase, Users, CalendarCheck, FileText } from "lucide-react";
import { toast } from "sonner";

import { useAuth } from "@/contexts/AuthContext";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { to: "/dashboard", label: "仪表盘", icon: LayoutDashboard },
  { to: "/positions", label: "岗位管理", icon: Briefcase },
  { to: "/candidates", label: "候选人", icon: Users },
  { to: "/interviews", label: "面试", icon: CalendarCheck },
  { to: "/reports", label: "报告", icon: FileText },
];

export function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    toast.success("已退出登录");
    navigate("/login", { replace: true });
  };

  return (
    <div className="flex h-screen bg-background">
      {/* 侧边栏 */}
      <aside className="w-60 border-r bg-card flex flex-col">
        {/* Logo + 系统名称 */}
        <div className="h-20 flex items-center gap-3 px-4 border-b">
          <img src="/logo.jpg" alt="星浩AI" className="h-10 w-auto rounded" />
          <div className="flex flex-col">
            <span className="text-sm font-bold">星浩AI</span>
            <span className="text-xs text-muted-foreground">智能面试系统</span>
          </div>
        </div>

        {/* 导航 */}
        <nav className="flex-1 p-4 space-y-1">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                )
              }
            >
              <item.icon className="h-4 w-4" />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        {/* 用户信息 */}
        <div className="p-4 border-t">
          <div className="text-sm font-medium">{user?.username || "用户"}</div>
          <div className="text-xs text-muted-foreground mb-3">
            {user?.email}
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors w-full"
          >
            <LogOut className="h-4 w-4" />
            退出登录
          </button>
        </div>

        {/* 星浩AI 底部品牌 */}
        <div className="p-3 border-t bg-muted/30">
          <p className="text-xs text-center text-muted-foreground mb-2">
            由 <span className="font-medium text-primary">星浩AI</span> 驱动
          </p>
          <p className="text-xs text-center text-muted-foreground mb-2">
            关注公众号「星浩AI」
          </p>
          <div className="flex justify-center">
            <img src="/wechat.jpg" alt="微信公众号二维码" className="w-20 h-20 rounded border" />
          </div>
        </div>
      </aside>

      {/* 主内容 */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}