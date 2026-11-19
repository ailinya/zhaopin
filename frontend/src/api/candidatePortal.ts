/**
 * CandidatePortal API 客户端
 */
import { apiClient } from "./client";

export interface InterviewInfo {
  interview_id: number;
  candidate_name: string;
  position_name: string;
  time: string;
  status: number;
  question_count: number;
  answered_count: number;
  voice_reading: boolean;
}

export interface Question {
  id: number;
  text: string;
}

export interface SubmitAnswerResponse {
  status: string;
  transcription_pending: boolean;
  answered_count: number;
  next_question: Question;
}

export const candidatePortalApi = {
  /**
   * 获取面试信息（通过 URL token）
   */
  async getInfo(token: string): Promise<InterviewInfo> {
    const { data } = await apiClient.get<{ data: InterviewInfo }>(`/api/candidate/${token}/info`);
    return data.data;
  },

  /**
   * 获取下一题
   */
  async getNextQuestion(token: string, afterId: number = 0): Promise<Question> {
    const { data } = await apiClient.get<{ data: Question }>(
      `/api/candidate/${token}/questions/next`,
      { params: { after: afterId } }
    );
    return data.data;
  },

  /**
   * 提交答案（multipart）
   */
  async submitAnswer(token: string, questionId: number, audioBlob: Blob): Promise<SubmitAnswerResponse> {
    const formData = new FormData();
    formData.append("question_id", String(questionId));
    formData.append("audio_answer", audioBlob, "answer.webm");
    const { data } = await apiClient.post<{ data: SubmitAnswerResponse }>(
      `/api/candidate/${token}/answers`,
      formData,
      { headers: { "Content-Type": "multipart/form-data" } }
    );
    return data.data;
  },

  /**
   * 切换语音朗读设置
   */
  async toggleVoice(token: string, enabled: boolean): Promise<{ voice_reading: boolean }> {
    const { data } = await apiClient.patch<{ data: { voice_reading: boolean } }>(
      `/api/candidate/${token}/preferences`,
      { enabled }
    );
    return data.data;
  },
};