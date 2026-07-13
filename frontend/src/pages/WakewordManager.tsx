import { useEffect, useState, useRef } from 'react';
import {
  Table, Button, Slider, InputNumber, Typography, Tag, Space, message,
  Row, Col, Select,
} from 'antd';
import { CheckOutlined, CloseOutlined, QuestionOutlined, PlayCircleOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import {
  getThreshold, setThreshold, listRecords, updateCategory, getAudioUrl,
} from '../api/wakeword';
import type { WakewordRecord } from '../api/wakeword';

const { Title, Text } = Typography;

const categoryColors: Record<string, string> = {
  positive: 'green',
  negative: 'red',
  unclassified: 'default',
};
const categoryLabels: Record<string, string> = {
  positive: 'Positive',
  negative: 'Negative',
  unclassified: '未分类',
};

export default function WakewordManager() {
  const [threshold, setThresholdVal] = useState(0.7);
  const [records, setRecords] = useState<WakewordRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [categoryFilter, setCategoryFilter] = useState<string | undefined>();
  const [playing, setPlaying] = useState<number | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);

  const fetchThreshold = async () => {
    try {
      const t = await getThreshold();
      setThresholdVal(t);
    } catch {
      message.error('加载阈值失败');
    }
  };

  const fetchRecords = async () => {
    setLoading(true);
    try {
      const res = await listRecords({
        category: categoryFilter,
        limit: pageSize,
        offset: (page - 1) * pageSize,
      });
      setRecords(res.items);
      setTotal(res.total);
    } catch {
      message.error('加载记录失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchThreshold();
  }, []);

  useEffect(() => {
    fetchRecords();
  }, [page, pageSize, categoryFilter]);

  const handleThresholdSave = async () => {
    try {
      await setThreshold(threshold);
      message.success('阈值已保存');
    } catch {
      message.error('保存失败');
    }
  };

  const handleCategory = async (record: WakewordRecord, newCat: string) => {
    try {
      await updateCategory(record.id, newCat);
      message.success(`已标记为 ${categoryLabels[newCat]}`);
      fetchRecords();
    } catch {
      message.error('操作失败');
    }
  };

  const handlePlay = (id: number) => {
    setPlaying(id);
    if (audioRef.current) {
      audioRef.current.src = getAudioUrl(id);
      audioRef.current.play().catch(() => {
        message.error('播放失败');
        setPlaying(null);
      });
    }
  };

  const onAudioEnd = () => setPlaying(null);

  const formatTime = (t: string) => {
    const d = new Date(t + 'Z');
    return d.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });
  };

  const columns: ColumnsType<WakewordRecord> = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    { title: '唤醒词 ID', dataIndex: 'wakeword_id', key: 'wakeword_id', width: 120 },
    {
      title: '分数', dataIndex: 'score', key: 'score', width: 80,
      render: (s: number) => <Text strong>{(s * 100).toFixed(1)}%</Text>,
    },
    {
      title: '分类', dataIndex: 'category', key: 'category', width: 100,
      render: (c: string) => <Tag color={categoryColors[c]}>{categoryLabels[c] || c}</Tag>,
    },
    {
      title: '音频', key: 'audio', width: 80,
      render: (_, record) => (
        <Button
          type="link"
          size="small"
          icon={<PlayCircleOutlined />}
          loading={playing === record.id}
          onClick={() => handlePlay(record.id)}
        >
          播放
        </Button>
      ),
    },
    {
      title: '操作', key: 'action', width: 220,
      render: (_, record) => (
        <Space>
          {record.category !== 'positive' && (
            <Button type="link" size="small" icon={<CheckOutlined />}
                    style={{ color: '#52c41a' }}
                    onClick={() => handleCategory(record, 'positive')}>
              Positive
            </Button>
          )}
          {record.category !== 'negative' && (
            <Button type="link" size="small" icon={<CloseOutlined />}
                    style={{ color: '#ff4d4f' }}
                    onClick={() => handleCategory(record, 'negative')}>
              Negative
            </Button>
          )}
          {record.category !== 'unclassified' && (
            <Button type="link" size="small" icon={<QuestionOutlined />}
                    onClick={() => handleCategory(record, 'unclassified')}>
              重置
            </Button>
          )}
        </Space>
      ),
    },
    {
      title: '时间', dataIndex: 'created_at', key: 'created_at', width: 160,
      render: (t: string) => formatTime(t),
    },
  ];

  return (
    <div>
      {/* 阈值设置 */}
      <Row gutter={16} align="middle" style={{ marginBottom: 16 }}>
        <Col><Text strong>检测阈值：</Text></Col>
        <Col flex="300px">
          <Slider
            min={0.0}
            max={1.0}
            step={0.05}
            value={threshold}
            onChange={setThresholdVal}
          />
        </Col>
        <Col>
          <InputNumber
            min={0}
            max={1}
            step={0.05}
            value={threshold}
            onChange={(v) => setThresholdVal(v || 0.7)}
            style={{ width: 80 }}
          />
        </Col>
        <Col>
          <Button type="primary" onClick={handleThresholdSave}>保存阈值</Button>
        </Col>
      </Row>

      {/* 隐藏的 audio 播放器 */}
      <audio ref={audioRef} onEnded={onAudioEnd} style={{ display: 'none' }} />

      {/* 筛选 + 表格 */}
      <Row gutter={12} style={{ marginBottom: 12 }}>
        <Col>
          <Select
            style={{ width: 140 }}
            placeholder="全部类型"
            allowClear
            value={categoryFilter}
            onChange={(v) => { setCategoryFilter(v); setPage(1); }}
            options={[
              { label: '全部', value: undefined },
              { label: 'Positive', value: 'positive' },
              { label: 'Negative', value: 'negative' },
              { label: '未分类', value: 'unclassified' },
            ]}
          />
        </Col>
        <Col>
          <Button onClick={() => { setPage(1); fetchRecords(); }}>刷新</Button>
        </Col>
      </Row>

      <Table
        columns={columns}
        dataSource={records}
        rowKey="id"
        loading={loading}
        scroll={{ x: 'max-content' }}
        pagination={{
          current: page, pageSize, total,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p, ps) => { setPage(p); setPageSize(ps); },
        }}
      />
    </div>
  );
}
