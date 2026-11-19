/**
 * VoiceRecorder - 浏览器录音（Week 3 Day 2）
 *
 * 封装 MediaRecorder API：
 * - 申请麦克风权限
 * - 录音（webm/opus 编码）
 * - 计时器
 * - 停止后返回 Blob
 *
 * 用法：
 *   <VoiceRecorder onComplete={(blob) => upload(blob)} />
 */
import { useEffect, useRef, useState } from "react";
import { Mic, Square } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui";

interface VoiceRecorderProps {
  onComplete: (blob: Blob) => void;
  disabled?: boolean;
}

export function VoiceRecorder({ onComplete, disabled }: VoiceRecorderProps) {
  const [recording, setRecording] = useState(false);
  const [time, setTime] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);

  // 计时器
  useEffect(() => {
    if (recording) {
      timerRef.current = window.setInterval(() => {
        setTime((t) => t + 1);
      }, 1000);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [recording]);

  // 清理
  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
      }
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, []);

  async function start() {
    setError(null);
    setTime(0);
    chunksRef.current = [];

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // 选择 webm/opus（最广泛兼容）
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";

      const recorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mimeType });
        setRecording(false);
        setTime(0);
        onComplete(blob);

        // 清理 stream
        stream.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      };

      recorder.onerror = (e) => {
        setError(`录音错误: ${e.error?.name || "unknown"}`);
        setRecording(false);
      };

      recorder.start();
      setRecording(true);
    } catch (err: any) {
      setError(err?.message || "无法访问麦克风");
      toast.error("无法访问麦克风，请检查权限");
    }
  }

  function stop() {
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
    }
  }

  const minutes = Math.floor(time / 60);
  const seconds = time % 60;
  const displayTime = `${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;

  return (
    <div className="flex flex-col items-center gap-3">
      <Button
        size="lg"
        variant={recording ? "destructive" : "default"}
        onClick={recording ? stop : start}
        disabled={disabled}
        className="h-16 w-16 rounded-full p-0"
      >
        {recording ? <Square className="h-6 w-6" /> : <Mic className="h-6 w-6" />}
      </Button>
      {recording && (
        <div className="flex items-center gap-2 text-sm text-destructive animate-pulse">
          <span className="h-2 w-2 rounded-full bg-destructive" />
          录音中 {displayTime}
        </div>
      )}
      {!recording && time === 0 && (
        <p className="text-sm text-muted-foreground">
          {disabled ? "请先听完题目" : "点击开始作答"}
        </p>
      )}
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}