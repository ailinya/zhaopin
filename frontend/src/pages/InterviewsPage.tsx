/**
 * InterviewsPage - 面试管理
 */
import { useEffect, useState } from "react";
import { Plus, X } from "lucide-react";
import { toast } from "sonner";

import { interviewsApi, type Interview, type InterviewCreate, INTERVIEW_STATUS } from "@/api/interviews";
import { candidatesApi, type Candidate } from "@/api/candidates";
import { positionsApi, type Position, POSITION_STATUS } from "@/api/positions";
import { apiClient } from "@/api/client";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { Button, Input, Card, CardContent, CardHeader, CardTitle } from "@/components/ui";

const STATUS_COLORS: Record<number, string> = {
  0: "bg-gray-100 text-gray-600",
  1: "bg-blue-100 text-blue-600",
  2: "bg-yellow-100 text-yellow-600",
  3: "bg-purple-100 text-purple-600",
  4: "bg-green-100 text-green-600",
};

export function InterviewsPage() {
  const [interviews, setInterviews] = useState<Interview[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);

  // 创建表单
  const [candidateId, setCandidateId] = useState("");
  const [positionId, setPositionId] = useState<number | "">("");
  const [interviewer, setInterviewer] = useState("");

  useEffect(() => {
    load();
  }, []);

  async function load() {
    setLoading(true);
    try {
      const [i, c, p] = await Promise.all([
        interviewsApi.list({ page_size: 100 }),
        candidatesApi.list({ page_size: 100 }),
        positionsApi.list({ page_size: 100 }),
      ]);
      setInterviews(i.items);
      setCandidates(c.items);
      setPositions(p.items);
    } catch (err) {
      toast.error("加载失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate() {
    if (!candidateId || !positionId) {
      toast.error("请选择候选人和岗位");
      return;
    }
    setCreating(true);
    try {
      const result = await interviewsApi.create({
        candidate_id: candidateId,
        position_id: Number(positionId),
        interviewer: interviewer || undefined,
        start_time: Math.floor(Date.now() / 1000),
      } as InterviewCreate);
      const baseUrl = window.location.origin;
      const candidateUrl = `${baseUrl}/candidate-portal?token=${result.token}`;
      toast.success("面试已创建，候选人链接已复制到剪贴板");
      await navigator.clipboard.writeText(candidateUrl);
      setShowCreate(false);
      setCandidateId(""); setPositionId(""); setInterviewer("");
      load();
    } catch (err: any) {
      toast.error(err?.data?.msg || "创建失败");
    } finally {
      setCreating(false);
    }
  }

  async function copyLink(interview: Interview) {
    const baseUrl = window.location.origin;
    const url = `${baseUrl}/candidate-portal?token=${interview.token}`;
    try {
      await navigator.clipboard.writeText(url);
      toast.success("候选人链接已复制");
    } catch {
      // fallback
      prompt("候选人链接（请复制）：", url);
    }
  }

  async function downloadReport(interview: Interview) {
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

  const candidateMap = new Map(candidates.map((c) => [c.id, c.name]));
  const positionMap = new Map(positions.map((p) => [p.id, p.name]));

  const columns: DataTableColumn<Interview>[] = [
    { key: "id", header: "ID", render: (i) => `#${i.id}`, width: "60px" },
    { key: "candidate", header: "候选人", render: (i) => {
      const text = candidateMap.get(i.candidate_id) || "—";
      return <span className="block max-w-[140px] truncate" title={text}>{text}</span>;
    }, className: "max-w-[140px]" },
    { key: "position", header: "岗位", render: (i) => {
      const text = positionMap.get(i.position_id) || "—";
      return <span className="block max-w-[200px] truncate" title={text}>{text}</span>;
    }, className: "max-w-[200px]" },
    { key: "status", header: "状态", render: (i) => (
      <span className={`px-2 py-1 rounded-full text-xs ${STATUS_COLORS[i.status]}`}>
        {INTERVIEW_STATUS[i.status as keyof typeof INTERVIEW_STATUS]}
      </span>
    )},
    { key: "progress", header: "进度", render: (i) => {
      if (i.question_count == null) return "—";
      return (
        <div className="flex items-center gap-2 w-32">
          <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-primary"
              style={{ width: `${(i.answered_count / i.question_count) * 100}%` }}
            />
          </div>
          <span className="text-xs text-muted-foreground">
            {i.answered_count}/{i.question_count}
          </span>
        </div>
      );
    }},
    { key: "interviewer", header: "面试官", render: (i) => i.interviewer || "—" },
  ];

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">面试</h1>
          <p className="text-muted-foreground mt-1">管理面试安排与进度</p>
        </div>
        <Button onClick={() => setShowCreate(true)}>
          <Plus className="h-4 w-4" />
          新建面试
        </Button>
      </div>

      <DataTable
        columns={columns}
        data={interviews}
        rowKey={(i) => i.id}
        loading={loading}
        actions={[
          { label: "复制链接", onClick: copyLink },
          { label: "下载报告", onClick: downloadReport },
        ]}
        emptyMessage="还没有面试"
      />

      {showCreate && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
          onClick={() => setShowCreate(false)}
        >
          <Card className="w-full max-w-xl" onClick={(e) => e.stopPropagation()}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>新建面试</CardTitle>
                <button onClick={() => setShowCreate(false)}>
                  <X className="h-4 w-4" />
                </button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm font-medium">候选人 *</label>
                <select
                  value={candidateId}
                  onChange={(e) => setCandidateId(e.target.value)}
                  className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm"
                >
                  <option value="">请选择候选人</option>
                  {candidates.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} - {c.email}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">应聘岗位 *</label>
                <select
                  value={positionId}
                  onChange={(e) => setPositionId(Number(e.target.value))}
                  className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm"
                >
                  <option value="">请选择岗位</option>
                  {positions.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name} ({POSITION_STATUS[p.status]})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium">面试官</label>
                <Input
                  value={interviewer}
                  onChange={(e) => setInterviewer(e.target.value)}
                  placeholder="姓名（可选）"
                />
              </div>
              <p className="text-xs text-muted-foreground">
                创建后将自动启动 AI 出题流程，并生成候选人专属链接
              </p>
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="outline" onClick={() => setShowCreate(false)}>
                  取消
                </Button>
                <Button onClick={handleCreate} disabled={creating}>
                  {creating ? "创建中..." : "创建面试"}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}