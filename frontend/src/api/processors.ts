import client from './client';
import type { ProcessorListResponse, ProcessorActionResponse } from '../types/processor';

export async function listProcessors(): Promise<ProcessorListResponse> {
  const res = await client.get<ProcessorListResponse>('/processors');
  return res.data;
}

export async function reloadProcessors(): Promise<ProcessorActionResponse> {
  const res = await client.post<ProcessorActionResponse>('/processors/reload');
  return res.data;
}
