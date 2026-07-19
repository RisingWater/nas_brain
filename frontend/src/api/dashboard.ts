import client from './client';

export interface DashboardStats {
  system: {
    memory_services: Record<string, number>;
    memory_total_kb: number;
    cpu: { load_1m: number; load_5m: number; load_15m: number; cores: number; pct: number };
  };
  storage: {
    db_size: number;
    audio_size: number;
    tts_cache_size: number;
    log_size: number;
    limit: number;
  };
  brain: {
    total_requests: number;
    total_answers: number;
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    uptime_seconds: number;
  };
  active_users: { "5min": number; "1hour": number; "1day": number };
  daily: {
    date: string;
    total: number;
    answered: number;
    avg_ms: number;
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  }[];
}

export async function getDashboardStats(): Promise<DashboardStats> {
  const res = await client.get('/admin/dashboard/stats');
  return res.data;
}
