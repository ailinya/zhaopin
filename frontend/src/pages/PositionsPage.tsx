/**
 * PositionsPage - 岗位管理（Week 3 Day 1）
 *
 * 列表 + 创建/编辑/删除
 */
import { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { toast } from "sonner";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

import { positionsApi, type Position, type PositionCreate, POSITION_STATUS } from "@/api/positions";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { Button, Input, Card, CardContent, CardHeader, CardTitle } from "@/components/ui";

const positionSchema = z.object({
  name: z.string().min(1, "请输入岗位名称"),
  requirements: z.string().default(""),
  responsibilities: z.string().default(""),
  quantity: z.coerce.number().int().min(1, "需求人数必须 ≥ 1").default(1),
  status: z.coerce.number().int().min(0).max(2).default(0),
  recruiter: z.string().default(""),
});

type PositionForm = z.infer<typeof positionSchema>;

export function PositionsPage() {
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Position | null>(null);
  const [showForm, setShowForm] = useState(false);

  const { register, handleSubmit, reset, formState: { errors } } = useForm<PositionForm>({
    resolver: zodResolver(positionSchema),
    defaultValues: { quantity: 1, status: 0 },
  });

  useEffect(() => {
    load();
  }, []);

  async function load() {
    setLoading(true);
    try {
      const res = await positionsApi.list({ page_size: 100 });
      setPositions(res.items);
    } catch (err) {
      toast.error("加载岗位失败");
    } finally {
      setLoading(false);
    }
  }

  function openCreate() {
    setEditing(null);
    reset({ name: "", requirements: "", responsibilities: "", quantity: 1, status: 0, recruiter: "" });
    setShowForm(true);
  }

  function openEdit(p: Position) {
    setEditing(p);
    reset({
      name: p.name,
      requirements: p.requirements,
      responsibilities: p.responsibilities,
      quantity: p.quantity,
      status: p.status,
      recruiter: p.recruiter || "",
    });
    setShowForm(true);
  }

  async function onSubmit(data: PositionForm) {
    try {
      const payload = {
        ...data,
        status: data.status as 0 | 1 | 2,
      };
      if (editing) {
        await positionsApi.update(editing.id, payload);
        toast.success("岗位已更新");
      } else {
        await positionsApi.create(payload as PositionCreate);
        toast.success("岗位已创建");
      }
      setShowForm(false);
      load();
    } catch (err) {
      toast.error("保存失败");
    }
  }

  async function onDelete(p: Position) {
    if (!confirm(`确定删除岗位 "${p.name}" 吗？`)) return;
    try {
      await positionsApi.delete(p.id);
      toast.success("已删除");
      load();
    } catch (err: any) {
      const msg = err?.data?.msg || "删除失败（可能有关联候选人或面试）";
      toast.error(msg);
    }
  }

  const columns: DataTableColumn<Position>[] = [
    { key: "id", header: "ID", render: (p) => `#${p.id}`, width: "80px" },
    { key: "name", header: "岗位名称", render: (p) => (
      <div className="min-w-[200px] max-w-[280px]">
        <div className="font-medium truncate" title={p.name}>{p.name}</div>
        <div className="text-xs text-muted-foreground line-clamp-1" title={p.requirements}>
          {p.requirements || "—"}
        </div>
      </div>
    ), className: "min-w-[200px] max-w-[280px]" },
    { key: "status", header: "状态", render: (p) => (
      <span className="px-2 py-1 rounded-full text-xs bg-secondary">
        {POSITION_STATUS[p.status]}
      </span>
    )},
    { key: "quantity", header: "需求", render: (p) => `${p.quantity} 人`, width: "80px" },
    { key: "created", header: "创建时间", render: (p) =>
      new Date(p.created_at * 1000).toLocaleDateString("zh-CN")
    , width: "120px" },
  ];

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">岗位管理</h1>
          <p className="text-muted-foreground mt-1">管理招聘岗位</p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4" />
          新建岗位
        </Button>
      </div>

      <DataTable
        columns={columns}
        data={positions}
        rowKey={(p) => p.id}
        loading={loading}
        actions={[
          { label: "编辑", onClick: openEdit },
          { label: "删除", onClick: onDelete, variant: "destructive" },
        ]}
        emptyMessage="还没有岗位，点击右上角创建"
      />

      {/* 简单的编辑弹窗（用 dialog 模拟） */}
      {showForm && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
          onClick={() => setShowForm(false)}
        >
          <Card className="w-full max-w-2xl" onClick={(e) => e.stopPropagation()}>
            <CardHeader>
              <CardTitle>{editing ? "编辑岗位" : "新建岗位"}</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
                <div>
                  <label className="text-sm font-medium">岗位名称 *</label>
                  <Input {...register("name")} placeholder="如：后端工程师" />
                  {errors.name && <p className="text-sm text-destructive mt-1">{errors.name.message}</p>}
                </div>
                <div>
                  <label className="text-sm font-medium">岗位要求</label>
                  <textarea
                    {...register("requirements")}
                    rows={3}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    placeholder="技术栈、经验要求等"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">岗位职责</label>
                  <textarea
                    {...register("responsibilities")}
                    rows={3}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    placeholder="日常工作内容"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium">需求人数</label>
                    <Input type="number" {...register("quantity")} min={1} />
                  </div>
                  <div>
                    <label className="text-sm font-medium">状态</label>
                    <select
                      {...register("status")}
                      className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm"
                    >
                      <option value="0">未启动</option>
                      <option value="1">进行中</option>
                      <option value="2">已完成</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label className="text-sm font-medium">招聘负责人</label>
                  <Input {...register("recruiter")} placeholder="HR 用户名" />
                </div>
                <div className="flex justify-end gap-2 pt-4">
                  <Button type="button" variant="outline" onClick={() => setShowForm(false)}>
                    取消
                  </Button>
                  <Button type="submit">保存</Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}