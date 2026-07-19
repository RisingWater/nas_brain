import client from './client';

export interface TraceItem {
  id: number;
  request_id: string;
  protocol: string;
  user_id: string;
  content: string;
  stages: Record<string, number>;
  metadata: Record<string, any>;
  reply_skip: boolean;
  created_at: string;
}

export interface TraceStats {
  total_count: number;
  skip_count: number;
  protocol_breakdown: Record<string, number>;
  avg_total_ms: number;
  stage_avg: Record<string, number>;
}

export async function getTraceStats(): Promise<TraceStats> {
  const res = await client.get('/admin/request-traces/stats');
  return res.data;
}

export async function listTraces(params?: {
  limit?: number;
  offset?: number;
  protocol?: string;
  skip_skip?: boolean;
}): Promise<{ total: number; items: TraceItem[] }> {
  const res = await client.get('/admin/request-traces/list', { params });
  return res.data;
}

export async function getTrace(requestId: string): Promise<TraceItem> {
  const res = await client.get(`/admin/request-traces/${requestId}`);
  return res.data;
}
