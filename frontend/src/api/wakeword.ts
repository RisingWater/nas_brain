import client from './client';

export interface WakewordRecord {
  id: number;
  wakeword_id: string;
  file_path: string;
  score: number;
  category: 'positive' | 'negative' | 'unclassified';
  created_at: string;
}

export async function getThreshold(): Promise<number> {
  const { data } = await client.get('/admin/wakeword/threshold');
  return data.threshold;
}

export async function setThreshold(threshold: number): Promise<void> {
  await client.put('/admin/wakeword/threshold', { threshold });
}

export async function listRecords(params?: {
  category?: string;
  limit?: number;
  offset?: number;
}): Promise<{ total: number; items: WakewordRecord[] }> {
  const { data } = await client.get('/admin/wakeword/records', { params });
  return data;
}

export async function getRecord(recordId: number): Promise<WakewordRecord> {
  const { data } = await client.get(`/admin/wakeword/records/${recordId}`);
  return data;
}

export async function updateCategory(recordId: number, category: string): Promise<void> {
  await client.put(`/admin/wakeword/records/${recordId}/category`, { category });
}

export function getAudioUrl(recordId: number): string {
  return `/api/admin/wakeword/records/${recordId}/audio`;
}

export async function getFrameSamples(): Promise<number> {
  const { data } = await client.get('/admin/wakeword/frame-samples');
  return data.frame_samples;
}

export async function setFrameSamples(frame_samples: number): Promise<void> {
  await client.put('/admin/wakeword/frame-samples', { frame_samples });
}
