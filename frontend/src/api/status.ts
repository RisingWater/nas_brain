import client from './client';

export interface AIStatus {
  state: 'idle' | 'listening' | 'thinking' | 'operating' | 'speaking';
  label: string;
  changed_at: number;
  duration: number;
  speaker: string;
  extra: Record<string, unknown>;
}

export async function getAIStatus(): Promise<AIStatus> {
  const res = await client.get('/admin/ai-status');
  return res.data;
}

export async function setAIStatus(state: string, speaker = ''): Promise<void> {
  await client.post('/admin/ai-status', { state, speaker });
}
