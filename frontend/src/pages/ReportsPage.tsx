/**
 * ReportsPage - 报告列表（Week 3 Day 1 占位）
 */
import { useEffect, useState } from "react";
import { FileText, Download } from "lucide-react";
import { toast } from "sonner";

import { interviewsApi, type Interview, INTERVIEW_STATUS } from "@/api/interviews";
import { apiClient } from "@/api/client";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import { Card, CardContent } from "@/components/ui";

export function ReportsPage() {
  const [reports, setReports] = useState<Interview[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    load();
  }, []);

  async function load() {
    setLoading(true);
    try {
      const res = await interviewsApi.list({ status: 4, page_size: 100 });
      setReports(res.items);
    } catch (err) {
      toast.error("加载失败");
    } finally {
      setLoading(false);
    }
  }

  async function download(interview: Interview) {
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

  const columns: DataTableColumn<Interview>[] = [
    { key: "id", header: "ID", render: (i) => `#${i.id}`, width: "60px" },
    { key: "status", header: "状态", render: (i) => (
      <span className="px-2 py-1 rounded-full text-xs bg-green-100 text-green-600">
        {INTERVIEW_STATUS[i.status as keyof typeof INTERVIEW_STATUS]}
      </span>
    )},
    { key: "is_passed", header: "结果", render: (i) => (
      i.is_passed === 1 ? (
        <span className="text-green-600 font-medium">通过</span>
      ) : (
        <span className="text-red-600 font-medium">未通过</span>
      )
    )},
    { key: "interviewer", header: "面试官", render: (i) => {
      const text = i.interviewer || "—";
      return <span className="block max-w-[140px] truncate" title={text}>{text}</span>;
    }, className: "max-w-[140px]" },
    { key: "created", header: "生成时间", render: (i) =>
      new Date(i.updated_at * 1000).toLocaleString("zh-CN")
    },
  ];

  return (
    <div className="p-8 space-y-6">
      <div>
        <h1 className="text-3xl font-bold flex items-center gap-2">
          <FileText className="h-7 w-7" />
          报告
        </h1>
        <p className="text-muted-foreground mt-1">已生成的面试报告</p>
      </div>

      <Card>
        <CardContent className="pt-6">
          <DataTable
            columns={columns}
            data={reports}
            rowKey={(i) => i.id}
            loading={loading}
            actions={[
              {
                label: "下载",
                onClick: download,
                icon: <Download className="h-3 w-3" />,
              } as any,
            ]}
            emptyMessage="还没有已生成的报告"
          />
        </CardContent>
      </Card>
    </div>
  );
}