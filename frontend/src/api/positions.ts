/**
 * Position API 客户端（Week 3 Day 1）
 */
import { apiClient } from "./client";

// ===== Types（与后端 schemas/position.py 镜像）=====

export interface Position {
  id: number;
  name: string;
  requirements: string;
  responsibilities: string;
  quantity: number;
  status: 0 | 1 | 2;  // 0=未启动 / 1=进行中 / 2=已完成
  recruiter: string | null;
  created_at: number;
  updated_at: number;
}

export interface PositionCreate {
  name: string;
  requirements?: string;
  responsibilities?: string;
  quantity?: number;
  status?: 0 | 1 | 2;
  recruiter?: string;
}

export type PositionUpdate = Partial<PositionCreate>;

export interface PositionListResponse {
  items: Position[];
  total: number;
  page: number;
  page_size: number;
}

// ===== Status 标签 =====
export const POSITION_STATUS = {
  0: "未启动",
  1: "进行中",
  2: "已完成",
} as const;

// ===== API =====
export const positionsApi = {
  async list(params?: { status?: number; page?: number; page_size?: number }): Promise<PositionListResponse> {
    const { data } = await apiClient.get<{ data: PositionListResponse }>("/api/positions", { params });
    return data.data;
  },

  async get(id: number): Promise<Position> {
    const { data } = await apiClient.get<{ data: Position }>(`/api/positions/${id}`);
    return data.data;
  },

  async create(data: PositionCreate): Promise<Position> {
    const res = await apiClient.post<{ data: Position }>("/api/positions", data);
    return res.data.data;
  },

  async update(id: number, data: PositionUpdate): Promise<Position> {
    const res = await apiClient.put<{ data: Position }>(`/api/positions/${id}`, data);
    return res.data.data;
  },

  async delete(id: number): Promise<void> {
    await apiClient.delete(`/api/positions/${id}`);
  },
};