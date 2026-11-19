/**
 * CandidatePortalPage - 候选人面试页面（Week 3 Day 2）
 *
 * 完整流程：
 * 1. URL ?token=xxx → 拉面试信息
 * 2. 显示当前题目 + 自动朗读
 * 3. 候选人录音 → 提交
 * 4. 自动加载下一题
 * 5. 最后一题答完 → 提示面试完成
 *
 * 集成：
 * - QuestionReader（题目朗读）
 * - VoiceRecorder（录音）
 * - SSE（实时进度，本期先占位用轮询）
 */
import { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "react-router";
import { toast } from "sonner";
import { CheckCircle2, Loader2 } from "lucide-react";

import { candidatePortalApi, type InterviewInfo, type Question } from "@/api/candidatePortal";
import { VoiceRecorder } from "@/components/VoiceRecorder";
import { QuestionReader } from "@/components/QuestionReader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui";
import { Spinner } from "@/components/ui/Spinner";

type Status = "loading" | "not_started" | "questions_ready" | "in_progress" | "completed" | "error";

export function CandidatePortalPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");

  const [status, setStatus] = useState<Status>("loading");
  const [info, setInfo] = useState<InterviewInfo | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null);
  const [answeredCount, setAnsweredCount] = useState(0);
  const [questionCount, setQuestionCount] = useState(0);
  const [voiceReading, setVoiceReading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  // 初始加载
  useEffect(() => {
    if (!token) {
      setStatus("error");
      toast.error("面试链接无效（缺少 token）");
      return;
    }
    loadInfo();
  }, [token]);

  async function loadInfo() {
    if (!token) return;
    try {
      const data = await candidatePortalApi.getInfo(token);
      setInfo(data);
      setVoiceReading(data.voice_reading);
      setQuestionCount(data.question_count);
      setAnsweredCount(data.answered_count);

      if (data.status === 0) {
        setStatus("not_started");
      } else if (data.status >= 3) {
        setStatus("completed");
      } else {
        setStatus("in_progress");
        // 自动加载第一题
        loadNextQuestion(0);
      }
    } catch (err: any) {
      setStatus("error");
      toast.error(err?.data?.msg || "面试信息加载失败");
    }
  }

  async function loadNextQuestion(afterId: number) {
    if (!token) return;
    try {
      const q = await candidatePortalApi.getNextQuestion(token, afterId);
      if (q.id === 0) {
        // 面试已完成
        setStatus("completed");
        return;
      }
      setCurrentQuestion(q);
    } catch (err: any) {
      toast.error(err?.data?.msg || "加载题目失败");
    }
  }

  const handleAnswerComplete = useCallback(
    async (audioBlob: Blob) => {
      if (!token || !currentQuestion || submitting) return;
      setSubmitting(true);
      try {
        const result = await candidatePortalApi.submitAnswer(token, currentQuestion.id, audioBlob);
        setAnsweredCount(result.answered_count);
        toast.success("答案已提交");

        if (result.next_question.id === 0) {
          // 最后一题
          setCurrentQuestion(null);
          setStatus("completed");
          toast.success("🎉 面试已完成！请等待 HR 通知");
        } else {
          setCurrentQuestion(result.next_question);
        }
      } catch (err: any) {
        toast.error(err?.data?.msg || "提交失败");
      } finally {
        setSubmitting(false);
      }
    },
    [token, currentQuestion, submitting]
  );

  const handleVoiceToggle = async (enabled: boolean) => {
    setVoiceReading(enabled);
    if (token) {
      try {
        await candidatePortalApi.toggleVoice(token, enabled);
      } catch (err) {
        // 非关键失败
      }
    }
  };

  // ===== 渲染 =====

  if (status === "loading") {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="flex h-screen items-center justify-center">
        <Card className="max-w-md">
          <CardContent className="pt-6 text-center">
            <p className="text-destructive text-lg">面试链接无效</p>
            <p className="text-muted-foreground mt-2">请检查链接是否正确，或联系 HR</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (status === "not_started") {
    return (
      <div className="flex h-screen items-center justify-center bg-muted/30">
        <Card className="max-w-md">
          <CardHeader className="text-center">
            <CardTitle>面试尚未开始</CardTitle>
          </CardHeader>
          <CardContent className="text-center">
            <p className="text-muted-foreground">您的面试 {info?.time} 即将开始，请稍候</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (status === "completed") {
    return (
      <div className="flex h-screen items-center justify-center bg-muted/30">
        <Card className="max-w-md">
          <CardContent className="pt-6 text-center space-y-3">
            <CheckCircle2 className="h-16 w-16 text-green-500 mx-auto" />
            <h2 className="text-2xl font-bold">面试已完成！</h2>
            <p className="text-muted-foreground">
              共回答 {answeredCount} / {questionCount} 题
            </p>
            <p className="text-sm text-muted-foreground">请等待 HR 通知结果</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  // 答题中
  return (
    <div className="min-h-screen bg-muted/30 py-8">
      <div className="max-w-3xl mx-auto px-4 space-y-6">
        {/* 头部：候选人 + 进度 */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-start justify-between">
              <div>
                <h1 className="text-xl font-semibold">{info?.position_name}</h1>
                <p className="text-sm text-muted-foreground mt-1">
                  候选人：{info?.candidate_name}
                </p>
              </div>
              <div className="text-right">
                <div className="text-sm text-muted-foreground">进度</div>
                <div className="text-2xl font-bold">
                  {answeredCount} / {questionCount}
                </div>
              </div>
            </div>
            {/* 进度条 */}
            <div className="mt-4 h-2 bg-muted rounded-full overflow-hidden">
              <div
                className="h-full bg-primary transition-all"
                style={{ width: `${(answeredCount / Math.max(questionCount, 1)) * 100}%` }}
              />
            </div>
          </CardContent>
        </Card>

        {/* 题目区 */}
        {currentQuestion && (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">问题 {answeredCount + 1}</CardTitle>
                <QuestionReader
                  text={currentQuestion.text}
                  enabled={voiceReading}
                  onToggle={handleVoiceToggle}
                  autoPlay={true}
                />
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-lg leading-relaxed p-4 bg-muted/30 rounded-md min-h-24">
                {currentQuestion.text}
              </p>

              <div className="mt-8 flex flex-col items-center gap-4">
                <VoiceRecorder onComplete={handleAnswerComplete} disabled={submitting} />
                {submitting && (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    正在提交并转写...
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}