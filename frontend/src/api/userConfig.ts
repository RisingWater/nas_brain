import client from './client';

export interface UserConfig {
  user_id: string;
  strategy: 'smart' | 'direct';
  system_prompt: string | null;
  allowed_tools: string[] | null;
  short_term_window: number;
  group_at_only: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface UserConfigUpdate {
  strategy?: 'smart' | 'direct';
  system_prompt?: string | null;
  allowed_tools?: string[] | null;
  short_term_window?: number;
  group_at_only?: boolean;
}

export async function getUserConfig(userId: string): Promise<UserConfig> {
  const { data } = await client.get(`/admin/user-configs/${userId}`);
  return data.data;
}

export async function updateUserConfig(userId: string, payload: UserConfigUpdate): Promise<void> {
  await client.put(`/admin/user-configs/${userId}`, payload);
}

export async function resetUserConfig(userId: string): Promise<void> {
  await client.delete(`/admin/user-configs/${userId}`);
}

export interface ToolInfo {
  name: string;
  description: string;
}

export async function listTools(): Promise<ToolInfo[]> {
  const { data } = await client.get('/tools');
  return data.data;
}
