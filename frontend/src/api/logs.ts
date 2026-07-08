import client from './client';
import type { ApiResponse, LogFile, LogData } from '../types/log';

export async function listLogFiles(): Promise<ApiResponse<LogFile[]>> {
  const res = await client.get<ApiResponse<LogFile[]>>('/logs/files');
  return res.data;
}

export async function readLog(
  filename: string,
  params?: { lines?: number; offset?: number; keyword?: string; level?: string },
): Promise<ApiResponse<LogData>> {
  const res = await client.get<ApiResponse<LogData>>(`/logs/${filename}`, { params });
  return res.data;
}
