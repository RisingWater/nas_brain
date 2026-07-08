import client from './client';
import type { ToolsResponse, ToolActionResponse } from '../types/tool';

export async function listTools(): Promise<ToolsResponse> {
  const res = await client.get<ToolsResponse>('/tools');
  return res.data;
}

export async function reloadTools(): Promise<ToolActionResponse> {
  const res = await client.post<ToolActionResponse>('/tools/reload');
  return res.data;
}
