/**
 * SSE 事件 TypeScript 类型（§5 + §11.5 增量）
 *
 * 与后端 backend/app/schemas/events.py 一一对应
 * 后端生成 openapi.json 后可用 openapi-typescript 自动生成
 *
 * 14 种事件 + 类型守卫
 */

// ===== 通用基础 =====

type EventBase = {
  timestamp: string;  // ISO 8601
};

// ===== 14 种事件 =====

export interface ConnectedEvent extends EventBase {
  event: "connected";
  interview_id: number;
}

export interface InterviewCreatedEvent extends EventBase {
  event: "interview_created";
  interview_id: number;
  candidate_id: number;
  position_id: number;
  candidate_name: string;
  position_name: string;
}

export interface StatusChangedEvent extends EventBase {
  event: "status_changed";
  interview_id: number;
  from_status: number;
  to_status: number;
}

export interface ResumeUploadedEvent extends EventBase {
  event: "resume_uploaded";
  candidate_id: string;
  file_type: "pdf" | "docx";
  file_size: number;
}

export interface ResumeParseStartedEvent extends EventBase {
  event: "resume_parse_started";
  candidate_id: string;
}

export interface ResumeParseCompleteEvent extends EventBase {
  event: "resume_parse_complete";
  candidate_id: string;
  text_length: number;
  parser_used: "pdf" | "docx";
}

export interface ResumeParseFailedEvent extends EventBase {
  event: "resume_parse_failed";
  candidate_id: string;
  error_code:
    | "EMPTY_TEXT"
    | "SCANNED_PDF"
    | "PARSE_EXCEPTION"
    | "ENCRYPTED_PDF"
    | "CORRUPT_FILE";
  error_message: string;
}

export interface AudioUploadedEvent extends EventBase {
  event: "audio_uploaded";
  interview_id: number;
  question_id: number;
  file_type: "webm" | "wav" | "mp3";
  file_size: number;
  duration_seconds: number | null;
}

export interface TranscriptionStartedEvent extends EventBase {
  event: "transcription_started";
  interview_id: number;
  question_id: number;
}

export interface TranscriptionCompleteEvent extends EventBase {
  event: "transcription_complete";
  interview_id: number;
  question_id: number;
  text_length: number;
  duration_seconds: number;
}

export interface QuestionsGeneratingEvent extends EventBase {
  event: "questions_generating";
  interview_id: number;
  progress: number;  // 0.0 - 1.0
}

export interface QuestionsGeneratedEvent extends EventBase {
  event: "questions_generated";
  interview_id: number;
  count: number;
  difficulty_distribution: Record<string, number>;
}

export interface AnswerSubmittedEvent extends EventBase {
  event: "answer_submitted";
  interview_id: number;
  question_id: number;
  answered_count: number;
  total_count: number;
}

export interface ReportGeneratingEvent extends EventBase {
  event: "report_generating";
  interview_id: number;
}

export interface ReportReadyEvent extends EventBase {
  event: "report_ready";
  interview_id: number;
  report_id: number;
  download_url: string;
}

export interface SystemFailureEvent extends EventBase {
  event: "system_failure";
  interview_id: number | null;
  error_code: string;
  error_message: string;
  component: "whisper" | "llm" | "weasyprint" | "langgraph" | "db";
}

export interface InterviewCancelledEvent extends EventBase {
  event: "interview_cancelled";
  interview_id: number;
  reason: string;
  cancelled_by: string;  // "hr" | "system"
}

// ===== Union 类型 =====

export type InterviewEvent =
  | ConnectedEvent
  | InterviewCreatedEvent
  | StatusChangedEvent
  | ResumeUploadedEvent
  | ResumeParseStartedEvent
  | ResumeParseCompleteEvent
  | ResumeParseFailedEvent
  | AudioUploadedEvent
  | TranscriptionStartedEvent
  | TranscriptionCompleteEvent
  | QuestionsGeneratingEvent
  | QuestionsGeneratedEvent
  | AnswerSubmittedEvent
  | ReportGeneratingEvent
  | ReportReadyEvent
  | SystemFailureEvent
  | InterviewCancelledEvent;

export type SSEEventName = InterviewEvent["event"];

// ===== 状态常量 =====

export const InterviewStatus = {
  NOT_STARTED: 0,
  QUESTIONS_READY: 1,
  IN_PROGRESS: 2,
  COMPLETED: 3,
  REPORT_READY: 4,
} as const;

export type InterviewStatusCode = (typeof InterviewStatus)[keyof typeof InterviewStatus];

export const InterviewStatusLabels: Record<InterviewStatusCode, string> = {
  [InterviewStatus.NOT_STARTED]: "未开始",
  [InterviewStatus.QUESTIONS_READY]: "试题已备好",
  [InterviewStatus.IN_PROGRESS]: "进行中",
  [InterviewStatus.COMPLETED]: "完毕",
  [InterviewStatus.REPORT_READY]: "报告已生成",
};

// ===== 类型守卫 =====

export function isEventOfType<T extends SSEEventName>(
  event: InterviewEvent,
  type: T
): event is Extract<InterviewEvent, { event: T }> {
  return event.event === type;
}