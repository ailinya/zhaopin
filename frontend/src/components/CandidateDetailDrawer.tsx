/**
 * CandidateDetailDrawer - 候选人详情/解析结果右侧抽屉
 *
 * 显示状态：
 * - 0/1（待解析/解析中）→ spinner
 * - 2（成功）→ 解析文本 + 字符数 + 复制/下载（>5000字可展开/收起）
 * - 3（失败）→ 错误信息 + 重试按钮
 *
 * 拉取策略：打开时 fetch getResumeText；解析中/重试后用 2s setInterval 轮询直到离开 1。
 */
import { useEffect, useRef, useState } from "react";
import { Copy, Download, AlertCircle, Loader2, ChevronDown, ChevronUp, ScanText, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { candidatesApi, type Candidate, type ResumeTextResponse, PARSE_STATUS } from "@/api/candidates";
import { ApiError, apiClient } from "@/api/client";
import {
  Drawer, DrawerContent, DrawerHeader, DrawerTitle, DrawerDescription, DrawerFooter,
  ScrollArea, Button, Badge, Spinner,
} from "@/components/ui";
import { cn } from "@/lib/utils";

const RESUME_TYPE_LABEL: Record<0 | 1, string> = { 0: "PDF", 1: "DOCX" };

const POLL_INTERVAL_MS = 2000;
const POLL_MAX_TIMES = 30; // 60s 上限
const TEXT_COLLAPSE_THRESHOLD = 5000;

const PARSE_STATUS_COLOR: Record<number, string> = {
  0: "bg-gray-100 text-gray-600",
  1: "bg-blue-100 text-blue-600",
  2: "bg-green-100 text-green-600",
  3: "bg-red-100 text-red-600",
};

export interface CandidateDetailDrawerProps {
  candidate: Candidate | null;
  positionName?: string;
  onOpenChange: (open: boolean) => void;
  onReparseSuccess?: () => void;
}

type FetchState =
  | { kind: "loading" }
  | { kind: "data"; data: ResumeTextResponse; fromPoll: boolean }
  | { kind: "pending" }       // 409 RESUME_NOT_PARSED（status 0/1）
  | { kind: "error"; message: string };

export function CandidateDetailDrawer({
  candidate,
  positionName,
  onOpenChange,
  onReparseSuccess,
}: CandidateDetailDrawerProps) {
  const open = !!candidate;
  const [state, setState] = useState<FetchState>({ kind: "loading" });
  const [expanded, setExpanded] = useState(false);
  const [reparsing, setReparsing] = useState(false);
  const pollTimerRef = useRef<number | null>(null);
  const pollCountRef = useRef(0);

  // 打开/候选人变化 → 拉一次
  useEffect(() => {
    if (!candidate) return;
    void loadResumeText(candidate.id);
    return () => stopPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candidate?.id, open]);

  async function loadResumeText(id: string, isPoll = false) {
    if (!isPoll) setState({ kind: "loading" });
    try {
      const data = await candidatesApi.getResumeText(id);
      setState({ kind: "data", data, fromPoll: isPoll });
      // 仍在解析中（理论上不会发生，因为后端对 0/1 返回 409，但保险）
      if (data.parse_status === 1) {
        startPolling(id);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        // RESUME_NOT_PARSED(3001)：解析中 → 轮询
        if (err.code === 3001) {
          setState({ kind: "pending" });
          startPolling(id);
          return;
        }
        setState({ kind: "error", message: err.message });
        return;
      }
      const msg = err instanceof Error ? err.message : "未知错误";
      setState({ kind: "error", message: msg });
    }
  }

  function startPolling(id: string) {
    stopPolling();
    pollCountRef.current = 0;
    pollTimerRef.current = window.setInterval(async () => {
      pollCountRef.current += 1;
      if (pollCountRef.current > POLL_MAX_TIMES) {
        stopPolling();
        return;
      }
      try {
        const data = await candidatesApi.getResumeText(id);
        if (data.parse_status !== 1) {
          stopPolling();
          setState({ kind: "data", data, fromPoll: true });
          // 通知父组件刷新列表（让徽章更新）
          onReparseSuccess?.();
        }
      } catch (err) {
        if (!(err instanceof ApiError) || err.code !== 3001) {
          // 非"还在解析"的错误，停止轮询
          stopPolling();
        }
      }
    }, POLL_INTERVAL_MS);
  }

  function stopPolling() {
    if (pollTimerRef.current != null) {
      window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }

  async function handleCopy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      toast.success("已复制到剪贴板");
    } catch {
      toast.error("复制失败，请手动复制");
    }
  }

  function handleDownload(text: string, candidateId: string) {
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `resume_${candidateId}.txt`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  }

  async function handleReparse() {
    if (!candidate) return;
    setReparsing(true);
    try {
      await candidatesApi.reparse(candidate.id);
      toast.success("已重新解析，请稍候");
      setState({ kind: "pending" });
      startPolling(candidate.id);
    } catch (err: any) {
      const msg = err instanceof ApiError
        ? err.message
        : (err?.data?.msg || err?.message || "重试失败");
      toast.error(msg);
    } finally {
      setReparsing(false);
    }
  }

  // 下载原始简历（已有 endpoint，复用 client 直接走 axios）
  async function handleDownloadOriginal(id: string) {
    try {
      const response = await apiClient.get(candidatesApi.resumeUrl(id), {
        responseType: "blob",
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = `resume_${id}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      toast.error("下载失败");
    }
  }

  const data = state.kind === "data" ? state.data : null;
  const text = data?.resume_text ?? "";
  const truncated = text.length > TEXT_COLLAPSE_THRESHOLD && !expanded;
  const displayText = truncated ? text.slice(0, TEXT_COLLAPSE_THRESHOLD) : text;

  return (
    <Drawer direction="right" open={open} onOpenChange={onOpenChange}>
      <DrawerContent>
        <DrawerHeader>
          <DrawerTitle>
            {candidate?.name ?? "候选人详情"}
          </DrawerTitle>
          <DrawerDescription className="space-y-1">
            {candidate && (
              <>
                <div className="text-sm text-muted-foreground">
                  {candidate.email}
                  {positionName && <span> · {positionName}</span>}
                </div>
                <div className="flex items-center gap-2 flex-wrap pt-1">
                  <Badge variant="outline">
                    {RESUME_TYPE_LABEL[candidate.resume_type as 0 | 1]}
                  </Badge>
                  {data && (
                    <span
                      className={cn(
                        "px-2 py-0.5 rounded-full text-xs",
                        PARSE_STATUS_COLOR[data.parse_status] ?? PARSE_STATUS_COLOR[0],
                      )}
                    >
                      {PARSE_STATUS[data.parse_status]}
                    </span>
                  )}
                  {data?.is_scanned_document && (
                    <Badge variant="warning" className="gap-1">
                      <ScanText className="h-3 w-3" />
                      扫描件
                    </Badge>
                  )}
                </div>
              </>
            )}
          </DrawerDescription>
        </DrawerHeader>

        <ScrollArea className="flex-1 min-h-0">
          <div className="p-6 space-y-4">
            {state.kind === "loading" && (
              <div className="flex flex-col items-center justify-center gap-3 py-16 text-muted-foreground">
                <Spinner size="lg" />
                <span>加载中…</span>
              </div>
            )}

            {state.kind === "pending" && (
              <div className="flex flex-col items-center justify-center gap-3 py-16 text-muted-foreground">
                <Loader2 className="h-8 w-8 animate-spin" />
                <span>解析中，请稍候…</span>
              </div>
            )}

            {state.kind === "error" && (
              <div className="space-y-3">
                <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                  <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                  <div>
                    <div className="font-medium">加载失败</div>
                    <div className="text-red-600/80 mt-1">{state.message}</div>
                  </div>
                </div>
                {candidate && (
                  <Button
                    variant="outline"
                    onClick={() => loadResumeText(candidate.id)}
                  >
                    重试
                  </Button>
                )}
              </div>
            )}

            {state.kind === "data" && state.data.parse_status === 2 && (
              <>
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>
                    共 {text.length.toLocaleString("zh-CN")} 字符
                    {state.data.parsed_at && (
                      <> · 解析于 {new Date(state.data.parsed_at * 1000).toLocaleString("zh-CN")}</>
                    )}
                  </span>
                  {text.length > TEXT_COLLAPSE_THRESHOLD && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setExpanded(!expanded)}
                    >
                      {expanded ? (
                        <>
                          <ChevronUp className="h-3 w-3" />
                          收起
                        </>
                      ) : (
                        <>
                          <ChevronDown className="h-3 w-3" />
                          展开全部
                        </>
                      )}
                    </Button>
                  )}
                </div>
                <pre className="whitespace-pre-wrap break-words rounded-md border bg-muted/30 p-4 text-sm font-mono leading-relaxed max-h-[60vh] overflow-y-auto">
                  {displayText}
                </pre>
                {truncated && (
                  <div className="text-xs text-muted-foreground text-center">
                    仅显示前 {TEXT_COLLAPSE_THRESHOLD.toLocaleString("zh-CN")} 字符，剩余 {text.length - TEXT_COLLAPSE_THRESHOLD} 字符已隐藏
                  </div>
                )}
              </>
            )}

            {state.kind === "data" && state.data.parse_status === 3 && (
              <div className="space-y-4">
                <div className="flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                  <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                  <div className="flex-1">
                    <div className="font-medium">解析失败</div>
                    <div className="text-red-600/80 mt-1 break-words">
                      {state.data.parse_error || "未知错误"}
                    </div>
                  </div>
                </div>
                <Button
                  onClick={handleReparse}
                  disabled={reparsing}
                >
                  <RefreshCw className={cn("h-4 w-4", reparsing && "animate-spin")} />
                  {reparsing ? "重试中…" : "重试解析"}
                </Button>
              </div>
            )}
          </div>
        </ScrollArea>

        <DrawerFooter className="flex-row justify-end gap-2">
          {data?.parse_status === 2 && text && (
            <>
              <Button
                variant="outline"
                onClick={() => handleCopy(text)}
              >
                <Copy className="h-4 w-4" />
                复制全文
              </Button>
              <Button
                variant="outline"
                onClick={() => candidate && handleDownload(text, candidate.id)}
              >
                <Download className="h-4 w-4" />
                下载为 .txt
              </Button>
            </>
          )}
          {candidate && (
            <Button
              variant="ghost"
              onClick={() => candidate && handleDownloadOriginal(candidate.id)}
            >
              <Download className="h-4 w-4" />
              下载原始简历
            </Button>
          )}
        </DrawerFooter>
      </DrawerContent>
    </Drawer>
  );
}
