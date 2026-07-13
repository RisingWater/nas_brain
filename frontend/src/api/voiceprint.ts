import client from './client';

export interface Voiceprint {
  id: number;
  user_id: string;
  audio_path: string;
  vp_type: 'auto' | 'manual';
  created_at: string;
}

export interface DetectUserResult {
  user_id: string;
  display_name: string;
  avg_sim: number;
  count: number;
}

export interface DetectResult {
  best_user_id: string | null;
  best_name: string;
  best_avg: number;
  users: DetectUserResult[];
}

export async function getThreshold(): Promise<number> {
  const { data } = await client.get('/admin/voiceprints/threshold');
  return data.threshold;
}

export async function setThreshold(threshold: number): Promise<void> {
  await client.put('/admin/voiceprints/threshold', { threshold });
}

export async function listVoiceprints(userId?: string): Promise<Voiceprint[]> {
  const params = userId ? { user_id: userId } : {};
  const { data } = await client.get('/admin/voiceprints', { params });
  return data.items;
}

export async function enrollVoiceprint(
  userId: string, vector: number[], audioPath: string, vpType: string = 'auto'
): Promise<void> {
  await client.post('/admin/voiceprints/enroll', {
    user_id: userId,
    vector,
    audio_path: audioPath,
    vp_type: vpType,
  });
}

export async function uploadVoiceprint(userId: string, file: File): Promise<any> {
  const formData = new FormData();
  formData.append('user_id', userId);
  formData.append('file', file);
  const { data } = await client.post('/admin/voiceprints/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function moveVoiceprint(vpId: number, targetUserId: string): Promise<void> {
  await client.put(`/admin/voiceprints/${vpId}/move`, null, {
    params: { target_user_id: targetUserId },
  });
}

export async function deleteVoiceprint(vpId: number): Promise<void> {
  await client.delete(`/admin/voiceprints/${vpId}`);
}

export function getAudioUrl(vpId: number): string {
  return `/api/admin/voiceprints/${vpId}/audio`;
}

export async function detectVoiceprint(vector: number[]): Promise<DetectResult> {
  const { data } = await client.post('/admin/voiceprints/detect', { vector });
  return data;
}

export async function listUsers(): Promise<any[]> {
  const { data } = await client.get('/admin/users', { params: { limit: 500 } });
  return data.data.users;
}
