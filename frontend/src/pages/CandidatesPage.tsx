/**
 * CandidatesPage - 候选人管理
 */
import { useEffect, useState, useRef } from "react";
import { Upload, FileText } from "lucide-react";
import { toast } from "sonner";

import { candidatesApi, type Candidate, PARSE_STATUS } from "@/api/candidates";
import { positionsApi, type Position, POSITION_STATUS } from "@/api/positions";
import { apiClient, ApiError } from "@/api/client";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { Button, Input, Card, CardContent, CardHeader, CardTitle } from "@/components/ui";
import { CandidateDetailDrawer } from "@/components/CandidateDetailDrawer";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

const RESUME_TYPE = { 0: "PDF", 1: "DOCX" } as const;

export function CandidatesPage() {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [deleteCandidate, setDeleteCandidate] = useState<Candidate | null>(null);
  const [detailCandidate, setDetailCandidate] = useState<Candidate | null>(null);

  // 上传表单
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [positionId, setPositionId] = useState<number | "">("");
  const [file, setFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    load();
  }, []);

  async function load() {
    setLoading(true);
    try {
      const [c, p] = await Promise.all([
        candidatesApi.list({ page_size: 100 }),
        positionsApi.list({ page_size: 100 }),
      ]);
      setCandidates(c.items);
      setPositions(p.items);
    } catch (err) {
      toast.error("加载失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleUpload() {
    if (!name || !email || !positionId || !file) {
      toast.error("请填写完整信息并选择简历文件");
      return;
    }
    setUploading(true);
    try {
      await candidatesApi.upload({
        name,
        email,
        position_id: Number(positionId),
        file,
      });
      toast.success("上传成功，简历解析中...");
      setShowUpload(false);
      setName(""); setEmail(""); setPositionId(""); setFile(null);
      load();
    } catch (err: any) {
      const msg = err instanceof ApiError ? err.message : (err?.data?.msg || "上传失败");
      toast.error(msg);
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(c: Candidate) {
    try {
      await candidatesApi.delete(c.id);
      toast.success("已删除");
      load();
    } catch (err: any) {
      toast.error(err?.data?.msg || "删除失败");
    }
  }

  function confirmDelete(c: Candidate) {
    setDeleteCandidate(c);
  }

  async function handleConfirmDelete() {
    if (!deleteCandidate) return;
    try {
      await candidatesApi.delete(deleteCandidate.id);
      toast.success("已删除");
      setDeleteCandidate(null);
      load();
    } catch (err: any) {
      const msg = err instanceof ApiError ? err.message : (err?.data?.msg || "删除失败");
      toast.error(msg);
    }
  }

  const positionMap = new Map(positions.map((p) => [p.id, p.name]));

  const columns: DataTableColumn<Candidate>[] = [
    { key: "name", header: "姓名", render: (c) => (
      <span className="block max-w-[140px] truncate" title={c.name}>{c.name}</span>
    ), className: "max-w-[140px]" },
    { key: "email", header: "邮箱", render: (c) => (
      <span className="block max-w-[240px] truncate text-muted-foreground" title={c.email}>{c.email}</span>
    ), className: "max-w-[240px]" },
    { key: "position", header: "应聘岗位", render: (c) => {
      const text = positionMap.get(c.position_id) || `#${c.position_id}`;
      return <span className="block max-w-[200px] truncate" title={text}>{text}</span>;
    }, className: "max-w-[200px]" },
    { key: "resume_type", header: "简历", render: (c) => RESUME_TYPE[c.resume_type as 0 | 1] },
    { key: "parse_status", header: "解析状态", render: (c) => {
      const colors: Record<number, string> = {
        0: "bg-gray-100 text-gray-600",
        1: "bg-blue-100 text-blue-600",
        2: "bg-green-100 text-green-600",
        3: "bg-red-100 text-red-600",
      };
      return (
        <span className={`px-2 py-1 rounded-full text-xs ${colors[c.parse_status]}`}>
          {PARSE_STATUS[c.parse_status]}
        </span>
      );
    }},
    { key: "uploaded", header: "上传时间", render: (c) =>
      new Date(c.uploaded_at * 1000).toLocaleDateString("zh-CN"), width: "120px"
    },
  ];

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">候选人</h1>
          <p className="text-muted-foreground mt-1">管理候选人简历</p>
        </div>
        <Button onClick={() => setShowUpload(true)}>
          <Upload className="h-4 w-4" />
          上传候选人
        </Button>
      </div>

      <DataTable
        columns={columns}
        data={candidates}
        rowKey={(c) => c.id}
        loading={loading}
        actions={[
          { label: "查看解析", onClick: (c) => setDetailCandidate(c) },
          {
            label: "下载简历",
            onClick: async (c) => {
              try {
                const response = await apiClient.get(candidatesApi.resumeUrl(c.id), {
                  responseType: "blob",
                });
                const url = window.URL.createObjectURL(new Blob([response.data]));
                const link = document.createElement("a");
                link.href = url;
                link.setAttribute("download", `resume_${c.id}.pdf`);
                document.body.appendChild(link);
                link.click();
                link.remove();
                window.URL.revokeObjectURL(url);
              } catch (err) {
                toast.error("下载简历失败");
              }
            },
          },
          { label: "删除", onClick: confirmDelete, variant: "destructive" },
        ]}
        emptyMessage="还没有候选人，点击右上角上传"
      />

      {showUpload && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
          onClick={() => setShowUpload(false)}
        >
          <Card className="w-full max-w-xl" onClick={(e) => e.stopPropagation()}>
            <CardHeader>
              <CardTitle>上传候选人</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm font-medium">姓名 *</label>
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="张三" />
              </div>
              <div>
                <label className="text-sm font-medium">邮箱 *</label>
                <Input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="zhang@example.com"
                />
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
                <label className="text-sm font-medium">简历文件 (PDF/DOCX) *</label>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.docx"
                  onChange={(e) => setFile(e.target.files?.[0] || null)}
                  className="w-full text-sm"
                />
                {file && (
                  <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                    <FileText className="h-3 w-3" />
                    {file.name} ({(file.size / 1024).toFixed(1)} KB)
                  </p>
                )}
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="outline" onClick={() => setShowUpload(false)}>
                  取消
                </Button>
                <Button onClick={handleUpload} disabled={uploading}>
                  {uploading ? "上传中..." : "上传"}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* 删除确认弹框 */}
      <AlertDialog open={!!deleteCandidate} onOpenChange={(open) => !open && setDeleteCandidate(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除</AlertDialogTitle>
            <AlertDialogDescription>
              确定删除候选人 "{deleteCandidate?.name}" 吗？此操作将同时删除关联的面试记录，无法恢复。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmDelete} className="bg-red-600 hover:bg-red-700">
              删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* 候选人解析详情抽屉 */}
      <CandidateDetailDrawer
        candidate={detailCandidate}
        positionName={detailCandidate ? positionMap.get(detailCandidate.position_id) : undefined}
        onOpenChange={(o) => !o && setDetailCandidate(null)}
        onReparseSuccess={load}
      />
    </div>
  );
}