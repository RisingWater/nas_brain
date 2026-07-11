import client from './client';

export interface ChatMessage {
  id: number;
  user_id: string;
  role: 'user' | 'assistant' | 'tool' | 'processor';
  content: string | null;
  tool_calls: any;
  tool_name: string | null;
  tool_result: any;
  processor_name: string | null;
  protocol: string;
  chat_type: string;
  created_at: string;
}

export async function getChatHistory(
  userId: string,
  params?: { limit?: number; before_id?: number; since_id?: number }
): Promise<{ total: number; messages: ChatMessage[] }> {
  const { data } = await client.get(`/admin/chat-messages/${userId}`, { params });
  return data;
}

export async function searchChatHistory(
  keyword: string,
  userId?: string,
  hoursBack: number = 72,
  limit: number = 20
): Promise<{ total: number; messages: ChatMessage[] }> {
  const { data } = await client.get('/admin/chat-messages/search', {
    params: { keyword, user_id: userId, hours_back: hoursBack, limit },
  });
  return data;
}

export async function clearChatHistory(userId: string): Promise<void> {
  await client.delete(`/admin/chat-messages/${userId}`);
}

export async function sendAgentRequest(
  userId: string,
  text: string,
): Promise<{ text: string }> {
  const { data } = await client.post('/admin/agent-request', {
    protocol: 'web',
    request_id: `web_${Date.now().toString(36)}`,
    chat_type: 'private',
    user_id: userId,
    content_type: 'text',
    content: text,
    metadata: {},
  });
  return { text: data.data?.text || '' };
}
