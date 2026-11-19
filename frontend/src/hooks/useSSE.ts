/**
 * useSSE - EventSource Hook（Week 3 Day 2）
 *
 * 封装 SSE 长连接：
 * - 自动连接 + 重连（断线 3 秒后）
 * - on(event, handler) 订阅事件
 * - 返回连接状态 + 事件计数
 *
 * 用法：
 *   const { connected, events } = useSSE(`/api/interviews/${id}/events`);
 *   useEffect(() => sse.on("status_changed", (data) => setStatus(data.to_status)), []);
 */
import { useEffect, useRef, useState } from "react";

export interface SSEEvent {
  event: string;
  data: any;
}

export function useSSE(url: string | null) {
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const handlersRef = useRef<Map<string, Set<(data: any) => void>>>(new Map());
  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);

  // 注册事件 handler
  const on = (eventName: string, handler: (data: any) => void) => {
    if (!handlersRef.current.has(eventName)) {
      handlersRef.current.set(eventName, new Set());
    }
    handlersRef.current.get(eventName)!.add(handler);

    // 返回 unsubscribe 函数
    return () => {
      handlersRef.current.get(eventName)?.delete(handler);
    };
  };

  // 触发所有该事件的 handlers
  const dispatch = (eventName: string, data: any) => {
    const handlers = handlersRef.current.get(eventName);
    if (handlers) {
      handlers.forEach((h) => h(data));
    }
    // 同时触发通配符 handlers
    const wildcard = handlersRef.current.get("*");
    if (wildcard) {
      wildcard.forEach((h) => h({ event: eventName, data }));
    }
  };

  useEffect(() => {
    if (!url) {
      setConnected(false);
      return;
    }

    let stopped = false;

    const connect = () => {
      if (stopped) return;
      // 清理旧连接
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }

      const es = new EventSource(url, { withCredentials: false });
      eventSourceRef.current = es;

      es.addEventListener("open", () => {
        setConnected(true);
      });

      es.addEventListener("error", () => {
        setConnected(false);
        if (!stopped) {
          // 自动重连
          if (reconnectTimerRef.current) {
            clearTimeout(reconnectTimerRef.current);
          }
          reconnectTimerRef.current = window.setTimeout(connect, 3000);
        }
      });

      // 默认事件：把任何 event:xxx 消息解析后分发
      const knownEvents = [
        "status_changed",
        "questions_generating",
        "questions_generated",
        "answer_submitted",
        "report_generating",
        "report_ready",
        "system_failure",
        "interview_cancelled",
        "resume_parse_started",
        "resume_parse_complete",
        "resume_parse_failed",
      ];

      for (const evt of knownEvents) {
        es.addEventListener(evt, (e: MessageEvent) => {
          try {
            const data = JSON.parse(e.data);
            dispatch(evt, data);
            setEvents((prev) => [...prev, { event: evt, data }]);
          } catch {
            /* ignore parse error */
          }
        });
      }
    };

    connect();

    return () => {
      stopped = true;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, [url]);

  return { connected, events, on };
}