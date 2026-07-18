import client from './client';

export interface DashboardStats {
  system: {
    memory_kb: number;
    memory_mb: number;
    load_1m: number;
    load_5m: number;
    load_15m: number;
  };
  storage: {
    db: { size: number; path: string };
    audio: { total_size: number; users: { user_id: string; size: number; count: number }[] };
    tts_cache_size: number;
    log_size: number;
  };
  brain: {
    total_requests: number;
    total_answers: number;
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    uptime_seconds: number;
  };
  active_users: {
    "5min": number;
    "1hour": number;
    "1day": number;
  };
}

export async function getDashboardStats(): Promise<DashboardStats> {
  const res = await client.get('/admin/dashboard/stats');
  return res.data;
}
