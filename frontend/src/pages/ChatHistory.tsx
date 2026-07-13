import { useEffect, useState, useRef } from 'react';
import {
  Select, Input, Button, Typography, Spin, Space, Tag, message, Popconfirm,
  Row, Col,
} from 'antd';
import { SearchOutlined, ReloadOutlined, ArrowDownOutlined, SendOutlined, DeleteOutlined } from '@ant-design/icons';
import { getChatHistory, searchChatHistory, sendAgentRequest, clearChatHistory } from '../api/chatHistory';
import type { ChatMessage } from '../api/chatHistory';
import { listUsers } from '../api/strategy';

const { Title, Text, Paragraph } = Typography;

const roleConfig: Record<string, { color: string; label: string }> = {
  user: { color: '#1677ff', label: '用户' },
  assistant: { color: '#52c41a', label: 'AI' },
  tool: { color: '#faad14', label: '工具' },
  processor: { color: '#722ed1', label: '处理器' },
};

export default function ChatHistory() {
  const [users, setUsers] = useState<any[]>([]);
  const [selectedUser, setSelectedUser] = useState<string | undefined>();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [keyword, setKeyword] = useState('');
  const [searching, setSearching] = useState(false);
  const [inputText, setInputText] = useState('');
  const [sending, setSending] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const PAGE_SIZE = 50;

  useEffect(() => {
    listUsers().then(setUsers).catch(() => {});
  }, []);

  const fetchHistory = async (userId: string, beforeId?: number) => {
    if (!beforeId) setLoading(true);
    else setLoadingMore(true);
    try {
      const res = await getChatHistory(userId, {
        limit: PAGE_SIZE,
        before_id: beforeId,
      });
      if (beforeId) {
        setMessages((prev) => [...prev, ...res.messages]);
      } else {
        setMessages(res.messages);
      }
      setHasMore(res.messages.length >= PAGE_SIZE);
    } catch {
      message.error('加载聊天记录失败');
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  };

  const handleUserChange = (userId: string) => {
    setSelectedUser(userId);
    setKeyword('');
    setSearching(false);
    fetchHistory(userId);
  };

  const handleSearch = async () => {
    if (!keyword.trim() || !selectedUser) return;
    setSearching(true);
    setLoading(true);
    try {
      const res = await searchChatHistory(keyword.trim(), selectedUser, 720, 50);
      setMessages(res.messages);
      setHasMore(false);
    } catch {
      message.error('搜索失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSend = async () => {
    if (!selectedUser || !inputText.trim() || sending) return;
    const text = inputText.trim();
    setInputText('');
    setSending(true);
    try {
      await sendAgentRequest(selectedUser, text);
      // 重新加载消息列表
      const res = await getChatHistory(selectedUser, { limit: PAGE_SIZE });
      setMessages(res.messages);
      setHasMore(res.messages.length >= PAGE_SIZE);
      // 滚动到底部
      setTimeout(() => {
        if (containerRef.current) containerRef.current.scrollTop = containerRef.current.scrollHeight;
      }, 100);
    } catch {
      message.error('发送失败');
    } finally {
      setSending(false);
    }
  };

  const handleClear = async () => {
    if (!selectedUser) return;
    try {
      await clearChatHistory(selectedUser);
      message.success('聊天记录已清空');
      setMessages([]);
      setHasMore(false);
    } catch {
      message.error('清空失败');
    }
  };

  const handleLoadMore = () => {
    if (!selectedUser || !hasMore || loadingMore) return;
    const oldest = messages[messages.length - 1];
    if (oldest) fetchHistory(selectedUser, oldest.id);
  };

  const formatTime = (t: string) => {
    const d = new Date(t + 'Z');
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  };

  const renderMessage = (msg: ChatMessage) => {
    const cfg = roleConfig[msg.role] || { color: '#888', label: msg.role };
    let content = msg.content || '';
    let extraInfo = '';

    if (msg.role === 'tool') {
      extraInfo = `工具: ${msg.tool_name || '?'}`;
      try {
        const parsed = typeof msg.tool_result === 'string' ? JSON.parse(msg.tool_result) : msg.tool_result;
        content = parsed?.text || JSON.stringify(parsed, null, 2);
      } catch {
        content = String(msg.tool_result || '');
      }
    }
    if (msg.role === 'processor') {
      extraInfo = `处理器: ${msg.processor_name || '?'}`;
    }
    if (msg.role === 'assistant' && msg.tool_calls) {
      const calls = Array.isArray(msg.tool_calls) ? msg.tool_calls : [];
      extraInfo = `调用了 ${calls.length} 个工具: ${calls.map((tc: any) => tc.function?.name).join(', ')}`;
    }

    return (
      <div key={msg.id} style={{ marginBottom: 12, padding: '8px 12px', borderLeft: `3px solid ${cfg.color}`, background: '#fafafa', borderRadius: 4 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <Space>
            <Tag color={cfg.color}>{cfg.label}</Tag>
            {extraInfo && <Text type="secondary" style={{ fontSize: 12 }}>{extraInfo}</Text>}
          </Space>
          <Text type="secondary" style={{ fontSize: 11 }}>{formatTime(msg.created_at)}</Text>
        </div>
        <Paragraph style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          {content || <Text type="secondary">（空）</Text>}
        </Paragraph>
      </div>
    );
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 120px)' }}>
      {/* 工具栏 */}
      <Row gutter={12} style={{ marginBottom: 12 }} align="middle">
        <Col flex="200px">
          <Select
            style={{ width: '100%' }}
            placeholder="选择用户"
            allowClear
            showSearch
            value={selectedUser}
            onChange={handleUserChange}
            filterOption={(v, option) => (option?.label as string || '').includes(v)}
            options={users.map((u) => ({
              label: `${u.display_name} (${u.user_id})`,
              value: u.user_id,
            }))}
          />
        </Col>
        <Col flex="auto">
          <Input.Search
            placeholder="搜索聊天内容"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onSearch={handleSearch}
            enterButton={<><SearchOutlined /> 搜索</>}
            disabled={!selectedUser}
          />
        </Col>
        <Col>
          <Button icon={<ReloadOutlined />} onClick={() => selectedUser && handleUserChange(selectedUser)}
                  disabled={!selectedUser}>刷新</Button>
        </Col>
        <Col>
          {selectedUser && (
            <Popconfirm title="确定清空该用户所有聊天记录？" onConfirm={handleClear} okText="确定" cancelText="取消">
              <Button icon={<DeleteOutlined />} danger>清空</Button>
            </Popconfirm>
          )}
        </Col>
      </Row>

      {/* 消息列表 */}
      <div ref={containerRef} style={{ flex: 1, overflow: 'auto', padding: '0 4px' }}>
        {searching && (
          <div style={{ textAlign: 'center', marginBottom: 8 }}>
            <Text type="secondary">搜索模式 — 仅显示匹配结果</Text>
            <Button type="link" size="small" onClick={() => selectedUser && handleUserChange(selectedUser)}>
              清除搜索
            </Button>
          </div>
        )}

        {loading ? (
          <div style={{ textAlign: 'center', padding: 60 }}><Spin size="large" /></div>
        ) : !selectedUser ? (
          <div style={{ textAlign: 'center', padding: 60, color: '#999' }}>请选择一个用户查看聊天记录</div>
        ) : messages.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 60, color: '#999' }}>暂无聊天记录</div>
        ) : (
          <>
            {messages.map(renderMessage)}
            {hasMore && (
              <div style={{ textAlign: 'center', padding: 12 }}>
                <Button onClick={handleLoadMore} loading={loadingMore} icon={<ArrowDownOutlined />}>
                  加载更多
                </Button>
              </div>
            )}
          </>
        )}

        {/* Web 聊天输入框 */}
        {selectedUser && (
          <div style={{ borderTop: '1px solid #e8e8e8', padding: '8px 0', display: 'flex', gap: 8 }}>
            <Input.TextArea
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onPressEnter={(e) => { if (!e.shiftKey) { e.preventDefault(); handleSend(); } }}
              placeholder="输入消息，Enter 发送，Shift+Enter 换行"
              rows={2}
              style={{ flex: 1 }}
              disabled={sending}
            />
            <Button type="primary" icon={<SendOutlined />} onClick={handleSend} loading={sending}
                    style={{ alignSelf: 'flex-end' }}>
              发送
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
