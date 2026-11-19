/**
 * InterviewDetailPage - 面试详情（Week 3 Day 2）
 *
 * 路径：/interviews/:id
 *
 * - 展示面试基本信息
 * - 通过 SSE 实时显示进度
 * - 显示报告下载（status >= 4）
 * - 候选人信息（关联 candidates 表）
 */
import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router";
import { ArrowLeft, Copy, CheckCircle2, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { interviewsApi, type Interview, INTERVIEW_STATUS } from "@/api/interviews";
import { candidatesApi, type Candidate } from "@/api/candidates";
import { positionsApi, type Position } from "@/api/positions";
import { apiClient } from "@/api/client";
import { useSSE } from "@/hooks/useSSE";
import { Card, CardContent, CardHeader, CardTitle, Button } from "@/components/ui";
import { Spinner } from "@/components/ui/Spinner";

const STATUS_COLORS: Record<number, string> = {
  0: "bg-gray-100 text-gray-600",
  1: "bg-blue-100 text-blue-600",
  2: "bg-yellow-100 text-yellow-600",
  3: "bg-purple-100 text-purple-600",
  4: "bg-green-100 text-green-600",
};

export function InterviewDetailPage() {
  const { id } = useParams<{ id: string }>();
  const interviewId = Number(id);
  const navigate = useNavigate();

  const [interview, setInterview] = useState<Interview | null>(null);
  const [candidate, setCandidate] = useState<Candidate | null>(null);
  const [position, setPosition] = useState<Position | null>(null);
  const [loading, setLoading] = useState(true);
  const [realtimeStatus, setRealtimeStatus] = useState<number | null>(null);
  const [realtimeAnswered, setRealtimeAnswered] = useState<number | null>(null);

  // 初始加载
  useEffect(() => {
    if (!interviewId) return;
    load();
  }, [interviewId]);

  async function load() {
    setLoading(true);
    try {
      const data = await interviewsApi.get(interviewId);
      setInterview(data);
      setRealtimeStatus(data.status);
      setRealtimeAnswered(data.answered_count);

      const [c, p] = await Promise.all([
        candidatesApi.get(data.candidate_id).catch(() => null),
        positionsApi.get(data.position_id).catch(() => null),
      ]);
      setCandidate(c);
      setPosition(p);
    } catch (err) {
      toast.error("加载失败");
    } finally {
      setLoading(false);
    }
  }

  // SSE 实时进度（一个 useSSE 调用，连 connection 状态 + 事件订阅）
  const sse = useSSE(interview ? `/api/interviews/${interview.id}/events` : null);

  useEffect(() => {
    if (!sse.on || !interview) return;
    const off1 = sse.on("status_changed", (data: any) => {
      setRealtimeStatus(data.to_status);
      toast.info(`状态变更为：${INTERVIEW_STATUS[data.to_status as keyof typeof INTERVIEW_STATUS]}`);
    });
    const off2 = sse.on("answer_submitted", (data: any) => {
      setRealtimeAnswered(data.answered_count);
    });
    const off3 = sse.on("report_ready", () => {
      toast.success("报告已生成！");
      load();
    });
    return () => { off1(); off2(); off3(); };
  }, [sse, interview]);

  // 显示最新状态（SSE 优先）
  const displayStatus = realtimeStatus ?? interview?.status ?? 0;
  const displayAnswered = realtimeAnswered ?? interview?.answered_count ?? 0;

  if (loading || !interview) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  function copyCandidateLink() {
    if (!interview) return;
    const baseUrl = window.location.origin;
    const url = `${baseUrl}/candidate-portal?token=${interview.token}`;
    navigator.clipboard.writeText(url).then(
      () => toast.success("候选人链接已复制"),
      () => toast.error("复制失败")
    );
  }

  async function downloadReport() {
    if (!interview) return;
    if (interview.status < 4) {
      toast.error("报告尚未生成");
      return;
    }
    try {
      const response = await apiClient.get(interviewsApi.reportUrl(interview.id), {
        responseType: "blob",
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `report_${interview.id}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      toast.error("下载报告失败");
    }
  }

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-6">
      {/* 顶部导航 */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => navigate("/interviews")}>
          <ArrowLeft className="h-4 w-4" />
          返回列表
        </Button>
        <h1 className="text-2xl font-bold">面试 #{interview.id}</h1>
        <span className={`px-2 py-1 rounded-full text-xs ${STATUS_COLORS[displayStatus]}`}>
          {INTERVIEW_STATUS[displayStatus as keyof typeof INTERVIEW_STATUS]}
        </span>
        <span className="text-xs text-muted-foreground">
          {sse.connected ? "🟢 SSE 已连接" : "⚪ SSE 未连接"}
        </span>
      </div>

      {/* 基本信息 */}
      <Card>
        <CardHeader>
          <CardTitle>面试信息</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-muted-foreground">候选人</dt>
              <dd className="font-medium">{candidate?.name || "—"}</dd>
              <dd className="text-xs text-muted-foreground">{candidate?.email}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">应聘岗位</dt>
              <dd className="font-medium">{position?.name || "—"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">面试官</dt>
              <dd className="font-medium">{interview.interviewer || "—"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">开始时间</dt>
              <dd className="font-medium">
                {new Date(interview.start_time * 1000).toLocaleString("zh-CN")}
              </dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      {/* 进度 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            答题进度
            {sse.connected && (
              <span className="text-xs text-green-600 flex items-center gap-1">
                <Loader2 className="h-3 w-3 animate-spin" />
                实时
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {interview.question_count != null ? (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span>已答 {displayAnswered} / 共 {interview.question_count} 题</span>
                <span className="text-muted-foreground">
                  {Math.round((displayAnswered / interview.question_count) * 100)}%
                </span>
              </div>
              <div className="h-3 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary transition-all"
                  style={{ width: `${(displayAnswered / interview.question_count) * 100}%` }}
                />
              </div>
              <div className="flex gap-4 text-xs text-muted-foreground pt-2">
                <span>难题: {interview.total_hard_questions}</span>
                <span>中等: {interview.total_medium_questions}</span>
                <span>简单: {interview.total_easy_questions}</span>
              </div>
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">题目尚未生成</p>
          )}
        </CardContent>
      </Card>

      {/* 操作 */}
      <Card>
        <CardHeader>
          <CardTitle>操作</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <Button onClick={copyCandidateLink}>
              <Copy className="h-4 w-4" />
              复制候选人链接
            </Button>
            <Button
              onClick={downloadReport}
              disabled={interview.status < 4}
              variant={interview.status >= 4 ? "default" : "secondary"}
            >
              {interview.status < 4 ? (
                <>
                  <Loader2 className="h-4 w-4" />
                  报告生成中...
                </>
              ) : (
                <>
                  <CheckCircle2 className="h-4 w-4" />
                  下载报告
                </>
              )}
            </Button>
            <Button
              variant="outline"
              onClick={() => window.open(`/candidate-portal?token=${interview.token}`, "_blank")}
            >
              打开候选人视图
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            候选人链接 token（可分享给候选人）：
            <code className="ml-2 px-2 py-1 bg-muted rounded">{interview.token}</code>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}