/**
 * DataTable - 通用列表组件（Week 3 Day 1）
 *
 * 通用列表（columns 配置 + 行操作 + loading / empty 状态）
 */
import { type ReactNode } from "react";

import { Skeleton } from "@/components/ui/Skeleton";
import { cn } from "@/lib/utils";

export interface DataTableColumn<T> {
  key: string;
  header: string;
  render: (item: T) => ReactNode;
  className?: string;
  width?: string;  // 如 "120px" 或 "20%"
}

export interface DataTableAction<T> {
  label: string;
  onClick: (item: T) => void;
  variant?: "default" | "destructive" | "ghost";
}

export interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  data: T[] | undefined;
  actions?: DataTableAction<T>[];
  rowKey: (item: T) => string | number;
  loading?: boolean;
  emptyMessage?: string;
  onRowClick?: (item: T) => void;
  actionWidth?: string;  // 操作列宽度，默认 "w-40"（160px，足以容纳"复制链接+下载报告"）
}

export function DataTable<T>({
  columns,
  data,
  actions,
  rowKey,
  loading,
  emptyMessage = "暂无数据",
  onRowClick,
  actionWidth = "w-40",
}: DataTableProps<T>) {
  if (loading) {
    return (
      <div className="space-y-2">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="rounded-lg border border-dashed p-12 text-center text-muted-foreground">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className="rounded-lg border overflow-hidden">
      <div className="overflow-x-auto">
      <table className="w-full">
        <thead className="bg-muted/50">
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                className={cn(
                  "px-4 py-3 text-left text-sm font-medium",
                  col.className
                )}
                style={col.width ? { width: col.width } : undefined}
              >
                {col.header}
              </th>
            ))}
            {actions && actions.length > 0 && (
              <th className={cn("px-4 py-3 text-right text-sm font-medium", actionWidth)}>
                操作
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {data.map((item) => (
            <tr
              key={rowKey(item)}
              onClick={onRowClick ? () => onRowClick(item) : undefined}
              className={cn(
                "border-t hover:bg-muted/30 transition-colors",
                onRowClick && "cursor-pointer"
              )}
            >
              {columns.map((col) => (
                <td
                  key={col.key}
                  className={cn("px-4 py-3 text-sm", col.className)}
                >
                  {col.render(item)}
                </td>
              ))}
              {actions && actions.length > 0 && (
                <td className={cn("px-4 py-3 text-right", actionWidth)}>
                  <div className="flex justify-end gap-2 whitespace-nowrap">
                    {actions.map((action, i) => (
                      <button
                        key={i}
                        onClick={(e) => {
                          e.stopPropagation();
                          action.onClick(item);
                        }}
                        className={cn(
                          "text-sm transition-colors whitespace-nowrap",
                          action.variant === "destructive"
                            ? "text-destructive hover:text-destructive/80"
                            : action.variant === "ghost"
                            ? "text-muted-foreground hover:text-foreground"
                            : "text-primary hover:text-primary/80"
                        )}
                      >
                        {action.label}
                      </button>
                    ))}
                  </div>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </div>
  );
}