import client from './client';
import type { ScheduleListResponse, ScheduleActionResponse } from '../types/schedule';

export async function listSchedules(params?: {
  done?: boolean;
  rtype?: string;
  keyword?: string;
  page?: number;
  page_size?: number;
}): Promise<ScheduleListResponse> {
  const res = await client.get<ScheduleListResponse>('/schedules', { params });
  return res.data;
}

export async function getSchedule(id: number): Promise<ScheduleActionResponse> {
  const res = await client.get<ScheduleActionResponse>(`/schedules/${id}`);
  return res.data;
}

export async function createSchedule(data: Record<string, unknown>): Promise<ScheduleActionResponse> {
  const res = await client.post<ScheduleActionResponse>('/schedules', data);
  return res.data;
}

export async function updateSchedule(id: number, data: Record<string, unknown>): Promise<ScheduleActionResponse> {
  const res = await client.put<ScheduleActionResponse>(`/schedules/${id}`, data);
  return res.data;
}

export async function deleteSchedule(id: number): Promise<ScheduleActionResponse> {
  const res = await client.delete<ScheduleActionResponse>(`/schedules/${id}`);
  return res.data;
}

export async function triggerSchedule(id: number): Promise<ScheduleActionResponse> {
  const res = await client.post<ScheduleActionResponse>(`/schedules/${id}/trigger`);
  return res.data;
}
