import { useEffect, useState, useCallback } from 'react';
import {
  Card, Table, Button, Row, Col, Typography, Space, message, Popconfirm, Statistic, Tooltip, Tag,
} from 'antd';
import {
  DeleteOutlined, ClearOutlined, ReloadOutlined, SoundOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { listTtsCache, getTtsCacheStats, deleteTtsCache, clearTtsCache } from '../api/tts';
import type { TtsCacheEntry, TtsCacheStats } from '../types/tts';

const { Title, Text } = Typography;

export default function TTSCacheManager() {
  const [entries, setEntries] = useState<TtsCacheEntry[]>([]);
  const [stats, setStats] = useState<TtsCacheStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [deleting, setDeleting] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [listRes, statsRes] = await Promise.all([listTtsCache(), getTtsCacheStats()]);
      setEntries(listRes.data);
      setStats(statsRes.data);
    } catch {
      message.error('获取缓存数据失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleDelete = async (id: string) => {
    setDeleting(id);
    try {
      await deleteTtsCache(id);
      message.success('已删除');
      await fetchData();
    } catch {
      message.error('删除失败');
    } finally {
      setDeleting(null);
    }
  };

  const handleClearAll = async () => {
    try {
      await clearTtsCache();
      message.success('已清空全部缓存');
      await fetchData();
    } catch {
      message.error('清空失败');
    }
  };

  const columns: ColumnsType<TtsCacheEntry> = [
    {
      title: '文本', dataIndex: 'text', key: 'text', width: 300,
      render: (text: string) => (
        <Tooltip title={text}>
          <Text style={{ fontSize: 13 }} ellipsis={{ tooltip: false }}>
            {text}
          </Text>
        </Tooltip>
      ),
    },
    {
      title: '大小', dataIndex: 'size_str', key: 'size', width: 80,
      render: (v: string) => <Text code>{v}</Text>,
    },
    {
      title: '创建时间', dataIndex: 'created_at_str', key: 'created_at', width: 170,
      responsive: ['md' as const],
    },
    {
      title: '最后访问', dataIndex: 'last_access_str', key: 'last_access', width: 170,
      responsive: ['lg' as const],
    },
    {
      title: '访问次数', dataIndex: 'hit_count', key: 'hit_count', width: 80, align: 'center',
      responsive: ['sm' as const],
      render: (v: number) => <Tag>{v}</Tag>,
    },
    {
      title: '后端', dataIndex: 'backend', key: 'backend', width: 100,
      responsive: ['sm' as const],
      render: (v: string) => <Text code>{v}</Text>,
    },
    {
      title: '操作', key: 'action', width: 60, align: 'center',
      render: (_, record) => (
        <Popconfirm
          title="删除这条缓存？"
          onConfirm={() => handleDelete(record.id)}
          okText="删除"
          cancelText="取消"
        >
          <Button
            size="small"
            danger
            icon={<DeleteOutlined />}
            loading={deleting === record.id}
          />
        </Popconfirm>
      ),
    },
  ];

  return (
    <>
      {/* 统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={6}>
          <Card size="small" hoverable>
            <Statistic
              title="缓存条目"
              value={stats?.valid_entries ?? 0}
              suffix={`/ ${stats?.total_entries ?? 0}`}
              valueStyle={{ fontSize: 24 }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={6}>
          <Card size="small" hoverable>
            <Statistic
              title="磁盘占用"
              value={stats?.total_size_str ?? '0 B'}
              valueStyle={{ fontSize: 24 }}
            />
          </Card>
        </Col>
      </Row>

      {/* 操作栏 */}
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {entries.length} 条缓存 {stats?.total_size ? `· 共 ${stats.total_size_str}` : ''}
          </Text>
        </Col>
        <Col>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={fetchData} loading={loading}>
              刷新
            </Button>
            {entries.length > 0 && (
              <Popconfirm
                title="确认清空所有 TTS 缓存？此操作不可恢复！"
                onConfirm={handleClearAll}
                okText="清空"
                cancelText="取消"
                okButtonProps={{ danger: true }}
              >
                <Button danger icon={<ClearOutlined />}>
                  清空全部
                </Button>
              </Popconfirm>
            )}
          </Space>
        </Col>
      </Row>

      {/* 缓存列表 */}
      <Table
        columns={columns}
        dataSource={entries.filter(e => e.file_exists)}
        rowKey="id"
        loading={loading}
        scroll={{ x: 'max-content' }}
        pagination={{ pageSize: 50, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
        size="small"
      />
    </>
  );
}
