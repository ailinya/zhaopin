/**
 * Candidate API 客户端
 */
import { apiClient } from "./client";

export interface Candidate {
  id: string;
  position_id: number;
  name: string;
  email: string;
  resume_type: 0 | 1;  // 0=PDF / 1=Word
  parse_status: 0 | 1 | 2 | 3;  // 0=待解析 / 1=解析中 / 2=成功 / 3=失败
  parse_error: string | null;
  is_scanned_document: boolean;
  uploaded_at: number;
  created_at: number;
}

export interface CandidateListResponse {
  items: Candidate[];
  total: number;
  page: number;
  page_size: number;
}

export const PARSE_STATUS = {
  0: "待解析",
  1: "解析中",
  2: "成功",
  3: "失败",
} as const;

export interface ResumeTextResponse {
  candidate_id: string;
  parse_status: 0 | 1 | 2 | 3;
  parse_error: string | null;
  resume_text: string | null;
  is_scanned_document: boolean | null;
  parsed_at: number | null;
  resume_type: 0 | 1;
}

export const candidatesApi = {
  async list(params?: { position_id?: number; page?: number; page_size?: number }): Promise<CandidateListResponse> {
    const { data } = await apiClient.get<{ data: CandidateListResponse }>("/api/candidates", { params });
    return data.data;
  },

  async get(id: string): Promise<Candidate> {
    const { data } = await apiClient.get<{ data: Candidate }>(`/api/candidates/${id}`);
    return data.data;
  },

  /**
   * 上传候选人（带简历）
   * 走 multipart/form-data
   */
  async upload(data: {
    name: string;
    email: string;
    position_id: number;
    file: File;
  }): Promise<{ candidate_id: string; parse_status: string }> {
    const formData = new FormData();
    formData.append("name", data.name);
    formData.append("email", data.email);
    formData.append("position_id", String(data.position_id));
    formData.append("resume", data.file);
    const res = await apiClient.post<{ data: { candidate_id: string; parse_status: string } }>(
      "/api/candidates",
      formData,
      { headers: { "Content-Type": "multipart/form-data" } }
    );
    return res.data.data;
  },

  async delete(id: string): Promise<void> {
    await apiClient.delete(`/api/candidates/${id}`);
  },

  /**
   * 获取候选人解析后的简历文本
   * - 200: 返回 { parse_status, resume_text?, parse_error?, ... }
   * - 404: 候选人不存在
   * - 409: 简历仍在解析中（parse_status in (0, 1)）
   */
  async getResumeText(id: string): Promise<ResumeTextResponse> {
    const { data } = await apiClient.get<{ data: ResumeTextResponse }>(
      `/api/candidates/${id}/resume-text`,
    );
    return data.data;
  },

  /**
   * 重新解析候选人简历（复用已存储的原始字节，无需重传）
   * - 200: 返回 { candidate_id, parse_status: "parsing" }
   * - 404: 候选人不存在
   * - 409 RESUME_RETRY_NOT_AVAILABLE: resume_content 为空
   * - 409 RESUME_NOT_PARSED: 当前正在解析中
   */
  async reparse(id: string): Promise<{ candidate_id: string; parse_status: string }> {
    const { data } = await apiClient.post<{ data: { candidate_id: string; parse_status: string } }>(
      `/api/candidates/${id}/reparse`,
    );
    return data.data;
  },

  /** 下载简历 URL（不通过 axios，前端 window.open） */
  resumeUrl(id: string): string {
    return `/api/candidates/${id}/resume`;
  },
};