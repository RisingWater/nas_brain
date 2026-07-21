import client from './client';

export interface AIStatus {
  state: 'idle' | 'listening' | 'thinking' | 'operating' | 'speaking';
  label: string;
  changed_at: number;
  duration: number;
  speaker: string;
  message: string;
  extra: Record<string, unknown>;
}

export async function getAIStatus(): Promise<AIStatus> {
  const res = await client.get('/admin/ai-status');
  return res.data;
}

export async function setAIStatus(state: string, speaker = ''): Promise<void> {
  await client.post('/admin/ai-status', { state, speaker });
}

/**
 * 连接 AI 状态 WebSocket，实时接收状态变更。
 * 返回 close 函数用于断开连接。
 *
 * 用法：
 *   const close = connectAIStatusWS(
 *     (data) => setStatus(data),
 *     () => console.log('WS 断开'),
 *   );
 *   // 清理时调用 close()
 */
export function connectAIStatusWS(
  onMessage: (status: AIStatus) => void,
  onDisconnect?: () => void,
): () => void {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/api/admin/ai-status/ws`;

  let ws: WebSocket | null = null;
  let closed = false;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  const connect = () => {
    if (closed) return;
    try {
      ws = new WebSocket(wsUrl);
    } catch {
      // 浏览器不支持 WebSocket 或 URL 非法
      onDisconnect?.();
      return;
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as AIStatus;
        onMessage(data);
      } catch {
        // 忽略解析失败
      }
    };

    ws.onclose = () => {
      if (!closed) {
        // 非主动关闭，3 秒后重连
        reconnectTimer = setTimeout(connect, 3000);
      }
    };

    ws.onerror = () => {
      ws?.close();
    };
  };

  connect();

  return () => {
    closed = true;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    if (ws) {
      ws.onclose = null; // 防止触发重连
      ws.close();
      ws = null;
    }
    onDisconnect?.();
  };
}
