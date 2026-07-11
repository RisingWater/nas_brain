import client from './client';

export async function getLongTermMemory(): Promise<string> {
  const { data } = await client.get('/admin/memory');
  return data.data.content;
}

export async function saveLongTermMemory(content: string): Promise<void> {
  await client.put('/admin/memory', { content });
}

export interface ChatSummary {
  id: number;
  user_id: string;
  summary: string;
  last_msg_id: number;
  created_at: string;
}

export async function getSummaries(userId: string): Promise<ChatSummary[]> {
  const { data } = await client.get(`/admin/chat-summaries/${userId}/list`);
  return data.items;  // db_services 返回 flat JSON
}
