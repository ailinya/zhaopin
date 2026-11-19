/**
 * QuestionReader - 浏览器 TTS 朗读（Week 3 Day 2）
 *
 * 封装 SpeechSynthesis API：
 * - 朗读题目文字（zh-CN）
 * - 可启用/停用
 * - 朗读中可停止
 */
import { useEffect, useRef, useState } from "react";
import { Volume2, VolumeX } from "lucide-react";

import { Button } from "@/components/ui";

interface QuestionReaderProps {
  text: string;
  enabled: boolean;
  onToggle?: (enabled: boolean) => void;
  autoPlay?: boolean;
}

export function QuestionReader({ text, enabled, onToggle, autoPlay = false }: QuestionReaderProps) {
  const [speaking, setSpeaking] = useState(false);
  const supported = typeof window !== "undefined" && "speechSynthesis" in window;
  const lastTextRef = useRef<string>("");

  // 当题目变化 + 启用 + autoPlay 时自动朗读
  useEffect(() => {
    if (autoPlay && enabled && supported && text !== lastTextRef.current) {
      lastTextRef.current = text;
      speak();
    } else {
      lastTextRef.current = text;
    }
  }, [text, enabled, autoPlay, supported]);

  // 组件卸载时停止朗读
  useEffect(() => {
    return () => {
      if (supported) {
        window.speechSynthesis.cancel();
      }
    };
  }, [supported]);

  function speak() {
    if (!supported) return;
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "zh-CN";
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    utterance.onstart = () => setSpeaking(true);
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);

    window.speechSynthesis.speak(utterance);
  }

  function stop() {
    if (!supported) return;
    window.speechSynthesis.cancel();
    setSpeaking(false);
  }

  function toggle() {
    if (!supported) return;
    if (speaking) {
      stop();
    } else {
      speak();
    }
  }

  if (!supported) return null;

  return (
    <div className="flex items-center gap-2">
      <Button variant="outline" size="sm" onClick={toggle}>
        {speaking ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
        {speaking ? "停止朗读" : "朗读题目"}
      </Button>
      {onToggle && (
        <label className="flex items-center gap-1 text-sm text-muted-foreground cursor-pointer">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => onToggle(e.target.checked)}
            className="rounded"
          />
          自动朗读
        </label>
      )}
    </div>
  );
}