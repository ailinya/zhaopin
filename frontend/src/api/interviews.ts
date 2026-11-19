/**
 * Interview API 客户端
 */
import { apiClient } from "./client";

export interface Interview {
  id: number;
  candidate_id: string;
  position_id: number;
  interviewer: string | null;
  start_time: number;
  end_time: number | null;
  status: 0 | 1 | 2 | 3 | 4;
  question_count: number | null;
  answered_count: number;
  total_hard_questions: number;
  total_medium_questions: number;
  total_easy_questions: number;
  is_passed: number | null;
  voice_reading: 0 | 1;
  token: string;
  langgraph_thread_id: string;
  created_at: number;
  updated_at: number;
}

export interface InterviewCreate {
  candidate_id: string;
  position_id?: number;
  interviewer?: string;
  start_time?: number;
  is_passed?: 0 | 1;
}

export type InterviewUpdate = Partial<InterviewCreate> & {
  status?: number;
};

export interface InterviewListResponse {
  items: Interview[];
  total: number;
  page: number;
  page_size: number;
}

export interface InterviewCreateResponse {
  id: number;
  token: string;
  status: number;
}

export const INTERVIEW_STATUS = {
  0: "未开始",
  1: "试题已备好",
  2: "进行中",
  3: "完毕",
  4: "报告已生成",
} as const;

export const interviewsApi = {
  async list(params?: {
    candidate_id?: string;
    position_id?: number;
    status?: number;
    page?: number;
    page_size?: number;
  }): Promise<InterviewListResponse> {
    const { data } = await apiClient.get<{ data: InterviewListResponse }>("/api/interviews", { params });
    return data.data;
  },

  async get(id: number): Promise<Interview> {
    const { data } = await apiClient.get<{ data: Interview }>(`/api/interviews/${id}`);
    return data.data;
  },

  async create(data: InterviewCreate): Promise<InterviewCreateResponse> {
    const res = await apiClient.post<{ data: InterviewCreateResponse }>("/api/interviews", data);
    return res.data.data;
  },

  async update(id: number, data: InterviewUpdate): Promise<Interview> {
    const res = await apiClient.put<{ data: Interview }>(`/api/interviews/${id}`, data);
    return res.data.data;
  },

  async delete(id: number): Promise<void> {
    await apiClient.delete(`/api/interviews/${id}`);
  },

  reportUrl(id: number): string {
    return `/api/interviews/${id}/report`;
  },
};