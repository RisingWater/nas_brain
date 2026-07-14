import client from './client';
import type {
  TtsCacheListResponse,
  TtsCacheStatsResponse,
  TtsCacheActionResponse,
} from '../types/tts';

export async function listTtsCache(): Promise<TtsCacheListResponse> {
  const res = await client.get<TtsCacheListResponse>('/tts/cache');
  return res.data;
}

export async function getTtsCacheStats(): Promise<TtsCacheStatsResponse> {
  const res = await client.get<TtsCacheStatsResponse>('/tts/cache/stats');
  return res.data;
}

export async function deleteTtsCache(id: string): Promise<TtsCacheActionResponse> {
  const res = await client.delete<TtsCacheActionResponse>(`/tts/cache/${id}`);
  return res.data;
}

export async function clearTtsCache(): Promise<TtsCacheActionResponse> {
  const res = await client.delete<TtsCacheActionResponse>('/tts/cache');
  return res.data;
}

export async function speakText(text: string): Promise<void> {
  await client.post('/speak/play', { text, sync: false });
}
