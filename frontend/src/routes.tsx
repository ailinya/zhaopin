/**
 * 路由配置（Week 3 Day 1）
 */
import { createBrowserRouter, Navigate } from "react-router";

import { LoginPage } from "./pages/LoginPage";
import { DashboardPage } from "./pages/DashboardPage";
import { PositionsPage } from "./pages/PositionsPage";
import { CandidatesPage } from "./pages/CandidatesPage";
import { InterviewsPage } from "./pages/InterviewsPage";
import { InterviewDetailPage } from "./pages/InterviewDetailPage";
import { ReportsPage } from "./pages/ReportsPage";
import { CandidatePortalPage } from "./pages/CandidatePortalPage";

import { AppLayout } from "./components/AppLayout";
import { AuthGuard } from "./components/AuthGuard";

export const router = createBrowserRouter([
  // ===== 公开 =====
  { path: "/login", Component: LoginPage },
  { path: "/candidate-portal", Component: CandidatePortalPage },

  // ===== HR 端（受 AuthGuard 保护，AppLayout 包裹）=====
  {
    path: "/",
    element: (
      <AuthGuard>
        <AppLayout />
      </AuthGuard>
    ),
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: "dashboard", Component: DashboardPage },
      { path: "positions", Component: PositionsPage },
      { path: "candidates", Component: CandidatesPage },
      { path: "interviews", Component: InterviewsPage },
      { path: "interviews/:id", Component: InterviewDetailPage },
      { path: "reports", Component: ReportsPage },
    ],
  },

  // ===== 未匹配 → dashboard（再由 AuthGuard 决定跳 login 或显示内容）=====
  { path: "*", element: <Navigate to="/" replace /> },
]);