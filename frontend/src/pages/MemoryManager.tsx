import { useEffect, useState } from 'react';
import {
  Card, Tabs, Input, Button, Select, Typography, message, Spin, Space, Tag, Empty, Modal,
} from 'antd';
import { EditOutlined, SaveOutlined, ReloadOutlined } from '@ant-design/icons';
import { getLongTermMemory, saveLongTermMemory, getSummaries } from '../api/memory';
import type { ChatSummary } from '../api/memory';
import { listUsers } from '../api/strategy';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

export default function MemoryManager() {
  // 长期记忆
  const [longTerm, setLongTerm] = useState('');
  const [editing, setEditing] = useState(false);
  const [editContent, setEditContent] = useState('');
  const [loadingLong, setLoadingLong] = useState(false);
  const [saving, setSaving] = useState(false);

  // 中期记忆
  const [users, setUsers] = useState<any[]>([]);
  const [selectedUser, setSelectedUser] = useState<string>();
  const [summaries, setSummaries] = useState<ChatSummary[]>([]);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [summaryDetail, setSummaryDetail] = useState<ChatSummary | null>(null);

  useEffect(() => {
    loadLongTerm();
    listUsers().then(setUsers).catch(() => {});
  }, []);

  const loadLongTerm = async () => {
    setLoadingLong(true);
    try {
      const content = await getLongTermMemory();
      setLongTerm(content);
      setEditContent(content);
    } catch {
      message.error('加载长期记忆失败');
    } finally {
      setLoadingLong(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await saveLongTermMemory(editContent);
      setLongTerm(editContent);
      setEditing(false);
      message.success('长期记忆已保存');
    } catch {
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleUserChange = async (userId: string) => {
    setSelectedUser(userId);
    setLoadingSummary(true);
    try {
      const items = await getSummaries(userId);
      setSummaries(items);
    } catch {
      setSummaries([]);
    } finally {
      setLoadingSummary(false);
    }
  };

  const formatTime = (t: string) => {
    if (!t) return '';
    const d = new Date(t + 'Z');
    return d.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });
  };

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16 }}>记忆管理</Title>

      <Tabs
        items={[
          {
            key: 'long',
            label: '长期记忆',
            children: (
              <Card>
                {loadingLong ? (
                  <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
                ) : editing ? (
                  <>
                    <TextArea
                      value={editContent}
                      onChange={(e) => setEditContent(e.target.value)}
                      rows={15}
                      style={{ fontFamily: 'monospace', fontSize: 13 }}
                      placeholder="在此编辑长期记忆…"
                    />
                    <Space style={{ marginTop: 12 }}>
                      <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={handleSave}>
                        保存
                      </Button>
                      <Button onClick={() => { setEditContent(longTerm); setEditing(false); }}>
                        取消
                      </Button>
                    </Space>
                  </>
                ) : (
                  <>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
                      <Text type="secondary">memory.md — 全局持久化记忆，LLM 每次调用时加载</Text>
                      <Space>
                        <Button size="small" icon={<ReloadOutlined />} onClick={loadLongTerm}>刷新</Button>
                        <Button size="small" type="primary" icon={<EditOutlined />} onClick={() => setEditing(true)}>
                          编辑
                        </Button>
                      </Space>
                    </div>
                    <div style={{
                      background: '#f5f5f5', padding: 16, borderRadius: 4,
                      whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: 13, minHeight: 200,
                    }}>
                      {longTerm || <Text type="secondary">（暂无长期记忆）</Text>}
                    </div>
                  </>
                )}
              </Card>
            ),
          },
          {
            key: 'mid',
            label: '中期记忆',
            children: (
              <Card>
                <Space style={{ marginBottom: 16 }}>
                  <Select
                    style={{ width: 300 }}
                    placeholder="选择用户查看中期记忆"
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
                  {selectedUser && (
                    <Button icon={<ReloadOutlined />} onClick={() => handleUserChange(selectedUser)}>
                      刷新
                    </Button>
                  )}
                </Space>

                {loadingSummary ? (
                  <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
                ) : !selectedUser ? (
                  <Empty description="请选择用户" />
                ) : summaries.length === 0 ? (
                  <Empty description="该用户暂无中期记忆" />
                ) : (
                  summaries.map((s) => (
                    <Card
                      key={s.id}
                      size="small"
                      style={{ marginBottom: 8 }}
                      extra={
                        <Button type="link" size="small" onClick={() => setSummaryDetail(s)}>
                          查看完整
                        </Button>
                      }
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          覆盖到消息 #{s.last_msg_id}
                        </Text>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {formatTime(s.created_at)}
                        </Text>
                      </div>
                      <Paragraph ellipsis={{ rows: 3 }} style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                        {s.summary}
                      </Paragraph>
                    </Card>
                  ))
                )}

                <Modal
                  title="中期记忆详情"
                  open={!!summaryDetail}
                  onCancel={() => setSummaryDetail(null)}
                  footer={null}
                  width={600}
                >
                  {summaryDetail && (
                    <>
                      <div style={{ marginBottom: 12 }}>
                        <Tag>#msg_id: {summaryDetail.last_msg_id}</Tag>
                        <Text type="secondary" style={{ marginLeft: 8 }}>{formatTime(summaryDetail.created_at)}</Text>
                      </div>
                      <div style={{ whiteSpace: 'pre-wrap', background: '#f5f5f5', padding: 12, borderRadius: 4 }}>
                        {summaryDetail.summary}
                      </div>
                    </>
                  )}
                </Modal>
              </Card>
            ),
          },
        ]}
      />
    </div>
  );
}
