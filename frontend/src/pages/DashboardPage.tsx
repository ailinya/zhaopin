/**
 * DashboardPage - 首页 KPI（Week 3 Day 1）
 */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { Briefcase, Users, CalendarCheck, FileText, TrendingUp } from "lucide-react";

import { positionsApi } from "@/api/positions";
import { candidatesApi } from "@/api/candidates";
import { interviewsApi, type Interview, INTERVIEW_STATUS } from "@/api/interviews";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { Skeleton } from "@/components/ui/Skeleton";

interface KPIs {
  positionsTotal: number;
  positionsActive: number;
  candidatesTotal: number;
  interviewsTotal: number;
  interviewsCompleted: number;
}

export function DashboardPage() {
  const navigate = useNavigate();
  const [kpis, setKpis] = useState<KPIs | null>(null);
  const [recentInterviews, setRecentInterviews] = useState<Interview[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    try {
      const [positions, candidates, interviews] = await Promise.all([
        positionsApi.list({ page_size: 100 }),
        candidatesApi.list({ page_size: 100 }),
        interviewsApi.list({ page_size: 10 }),  // 最近 10 个
      ]);
      setKpis({
        positionsTotal: positions.total,
        positionsActive: positions.items.filter((p) => p.status === 1).length,
        candidatesTotal: candidates.total,
        interviewsTotal: interviews.total,
        interviewsCompleted: interviews.items.filter((i) => i.status === 4).length,
      });
      setRecentInterviews(interviews.items);
    } catch (err) {
      console.error("Dashboard load failed", err);
    } finally {
      setLoading(false);
    }
  }

  const interviewColumns: DataTableColumn<Interview>[] = [
    { key: "id", header: "ID", render: (i) => `#${i.id}`, width: "80px" },
    { key: "status", header: "状态", render: (i) => (
      <span className="px-2 py-1 rounded-full text-xs bg-secondary">
        {INTERVIEW_STATUS[i.status as keyof typeof INTERVIEW_STATUS] || i.status}
      </span>
    )},
    { key: "interviewer", header: "面试官", render: (i) => i.interviewer || "-" },
    { key: "start_time", header: "开始时间", render: (i) =>
      new Date(i.start_time * 1000).toLocaleString("zh-CN")
    },
    { key: "answered_count", header: "进度", render: (i) =>
      `${i.answered_count} / ${i.question_count ?? "?"}`
    },
  ];

  if (loading) {
    return (
      <div className="p-8 space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold">仪表盘</h1>
        <p className="text-muted-foreground mt-1">系统整体概览</p>
      </div>

      {/* KPI 卡片 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          title="岗位总数"
          value={kpis?.positionsTotal ?? 0}
          subtitle={`${kpis?.positionsActive ?? 0} 个进行中`}
          icon={Briefcase}
          color="blue"
          onClick={() => navigate("/positions")}
        />
        <KPICard
          title="候选人"
          value={kpis?.candidatesTotal ?? 0}
          subtitle="已入库"
          icon={Users}
          color="green"
          onClick={() => navigate("/candidates")}
        />
        <KPICard
          title="面试"
          value={kpis?.interviewsTotal ?? 0}
          subtitle={`${kpis?.interviewsCompleted ?? 0} 个已出报告`}
          icon={CalendarCheck}
          color="orange"
          onClick={() => navigate("/interviews")}
        />
        <KPICard
          title="报告"
          value={kpis?.interviewsCompleted ?? 0}
          subtitle="已生成"
          icon={FileText}
          color="purple"
          onClick={() => navigate("/reports")}
        />
      </div>

      {/* 最近面试 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            最近面试
          </CardTitle>
        </CardHeader>
        <CardContent>
          <DataTable
            columns={interviewColumns}
            data={recentInterviews}
            rowKey={(i) => i.id}
            emptyMessage="还没有面试记录"
          />
        </CardContent>
      </Card>
    </div>
  );
}

function KPICard({
  title,
  value,
  subtitle,
  icon: Icon,
  color,
  onClick,
}: {
  title: string;
  value: number;
  subtitle: string;
  icon: React.ComponentType<{ className?: string }>;
  color: "blue" | "green" | "orange" | "purple";
  onClick?: () => void;
}) {
  const colors = {
    blue: "bg-blue-50 text-blue-600",
    green: "bg-green-50 text-green-600",
    orange: "bg-orange-50 text-orange-600",
    purple: "bg-purple-50 text-purple-600",
  };

  return (
    <Card
      className={`cursor-pointer hover:shadow-md transition-shadow ${onClick ? "" : ""}`}
      onClick={onClick}
    >
      <CardContent className="pt-6">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm text-muted-foreground">{title}</p>
            <p className="text-3xl font-bold mt-2">{value}</p>
            <p className="text-xs text-muted-foreground mt-2">{subtitle}</p>
          </div>
          <div className={`h-12 w-12 rounded-lg flex items-center justify-center ${colors[color]}`}>
            <Icon className="h-6 w-6" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}