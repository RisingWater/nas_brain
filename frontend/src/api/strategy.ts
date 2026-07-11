import client from './client';

export interface UserConfig {
  user_id: string;
  strategy: 'smart' | 'direct' | 'ignore';
  system_prompt: string | null;
  allowed_tools: string[] | null;
  allowed_processors: string[] | null;
  short_term_window: number;
  group_at_only: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface UserConfigUpdate {
  strategy?: 'smart' | 'direct' | 'ignore';
  system_prompt?: string | null;
  allowed_tools?: string[] | null;
  allowed_processors?: string[] | null;
  short_term_window?: number;
  group_at_only?: boolean;
}

export interface UserConfigListItem {
  user_id: string;
  strategy: string;
  display_name: string;
  user_type: string;
  wechat_name: string | null;
  short_term_window: number;
  group_at_only: boolean;
  updated_at: string | null;
}

export async function listUserConfigs(): Promise<UserConfigListItem[]> {
  const { data } = await client.get('/admin/user-configs');
  return data.items;  // db_services 返回 flat JSON
}

export async function getUserConfig(userId: string): Promise<UserConfig> {
  const { data } = await client.get(`/admin/user-configs/${userId}`);
  return data;  // db_services 返回 flat JSON
}

export async function updateUserConfig(userId: string, payload: UserConfigUpdate): Promise<void> {
  await client.put(`/admin/user-configs/${userId}`, payload);
}

export async function listUsers(): Promise<any[]> {
  const { data } = await client.get('/admin/users', { params: { limit: 500 } });
  return data.data.users;
}

export interface ToolInfo {
  name: string;
  description: string;
}

export async function listTools(): Promise<ToolInfo[]> {
  const { data } = await client.get('/tools');
  return data.data;
}

export interface ProcessorInfo {
  name: string;
  description: string;
}

export async function listProcessors(): Promise<ProcessorInfo[]> {
  const { data } = await client.get('/processors');
  return data.data;
}
