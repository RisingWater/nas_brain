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
