import { useEffect, useState } from 'react';
import { Table, Tag, Typography, Card, Descriptions, Spin, Button, Space, Divider, Progress } from 'antd';
import { ArrowLeftOutlined, ClockCircleOutlined } from '@ant-design/icons';
import { listTraces, getTrace } from '../api/traces';
import type { TraceItem } from '../api/traces';

const { Text, Title } = Typography;

function formatDur(ms: number): string {
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

const stageLabels: Record<string, string> = {
  wakeword: '唤醒',
  record_end: '录音结束',
  voiceprint_end: '声纹识别',
  stt_end: '语音转文字',
  brain_receive: 'Brain 收到',
  brain_done: 'Brain 完成',
  llm_first_done: 'LLM 首次回复',
  tool_call: '工具调用',
  tool_result: '工具返回',
  tts_end: 'TTS 合成',
  play_start: '开始播放',
  play_end: '播放结束',
};

const stageColors: Record<string, string> = {
  wakeword: '#722ed1',
  record_end: '#13c2c2',
  voiceprint_end: '#eb2f96',
  stt_end: '#fa8c16',
  brain_receive: '#1677ff',
  brain_done: '#52c41a',
  llm_first_done: '#2f54eb',
  tool_call: '#faad14',
  tool_result: '#a0d911',
  tts_end: '#1890ff',
  play_start: '#13c2c2',
  play_end: '#52c41a',
};

function calcDuration(stages: Record<string, number>, startKey: string, endKey: string): number | null {
  if (stages[startKey] && stages[endKey] && stages[endKey] >= stages[startKey]) {
    return stages[endKey] - stages[startKey];
  }
  return null;
}

function TraceDetail({ requestId, onBack }: { requestId: string; onBack: () => void }) {
  const [trace, setTrace] = useState<TraceItem | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getTrace(requestId).then(setTrace).catch(() => setTrace(null)).finally(() => setLoading(false));
  }, [requestId]);

  if (loading) return <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>;
  if (!trace) return <Text type="danger">未找到追踪记录</Text>;

  const stages = trace.stages || {};
  const meta = trace.metadata || {};
  const stageEntries = Object.entries(stages).sort(([, a], [, b]) => a - b);

  const durationPairs: { label: string; start: string; end: string; color: string }[] = [];

  if (stages.wakeword && stages.play_end) {
    durationPairs.push({ label: '总耗时', start: 'wakeword', end: 'play_end', color: '#1677ff' });
  }
  if (stages.wakeword && stages.record_end) {
    durationPairs.push({ label: '录音', start: 'wakeword', end: 'record_end', color: '#13c2c2' });
  }
  if (stages.record_end && stages.voiceprint_end) {
    durationPairs.push({ label: '声纹识别', start: 'record_end', end: 'voiceprint_end', color: '#eb2f96' });
  }
  if (stages.voiceprint_end && stages.stt_end) {
    durationPairs.push({ label: 'STT', start: 'voiceprint_end', end: 'stt_end', color: '#fa8c16' });
  }
  if (stages.brain_receive && stages.brain_done) {
    durationPairs.push({ label: 'Brain 处理', start: 'brain_receive', end: 'brain_done', color: '#2f54eb' });
  }
  if (stages.brain_receive && stages.llm_first_done) {
    durationPairs.push({ label: 'LLM 首次思考', start: 'brain_receive', end: 'llm_first_done', color: '#722ed1' });
  }
  if (stages.tts_end && stages.play_end) {
    durationPairs.push({ label: 'TTS→播放', start: 'tts_end', end: 'play_end', color: '#1890ff' });
  }

  const totalMs = stages.wakeword && stages.play_end ? stages.play_end - stages.wakeword : null;

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={onBack}>返回列表</Button>
      </Space>

      <Card size="small" style={{ marginBottom: 16 }}>
        <Descriptions column={4} size="small">
          <Descriptions.Item label="请求 ID"><Text code>{trace.request_id}</Text></Descriptions.Item>
          <Descriptions.Item label="协议"><Tag>{trace.protocol}</Tag></Descriptions.Item>
          <Descriptions.Item label="用户">{meta.user_id || trace.user_id || '-'}</Descriptions.Item>
          <Descriptions.Item label="耗时">{totalMs ? formatDur(totalMs) : '-'}</Descriptions.Item>
          {meta.speaker && <Descriptions.Item label="声纹">{meta.speaker}</Descriptions.Item>}
          {meta.tool && <Descriptions.Item label="工具">{meta.tool}</Descriptions.Item>}
          <Descriptions.Item label="内容"><Text copyable style={{ maxWidth: 300 }} ellipsis>{trace.content || '-'}</Text></Descriptions.Item>
          {meta.reply_summary && <Descriptions.Item label="回复"><Text copyable style={{ maxWidth: 300 }} ellipsis>{meta.reply_summary}</Text></Descriptions.Item>}
        </Descriptions>
      </Card>

      {/* 耗时条 */}
      {durationPairs.length > 0 && (
        <Card size="small" title="各阶段耗时" style={{ marginBottom: 16 }}>
          {durationPairs.map((pair) => {
            const dur = calcDuration(stages, pair.start, pair.end);
            if (!dur) return null;
            const pct = totalMs ? Math.min(100, (dur / totalMs) * 100) : 0;
            return (
              <div key={pair.label} style={{ marginBottom: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                  <Text style={{ fontSize: 13 }}>{pair.label}</Text>
                  <Text type="secondary" style={{ fontSize: 12 }}>{formatDur(dur)}</Text>
                </div>
                <Progress percent={Math.round(pct)} size="small" strokeColor={pair.color} showInfo={false} />
              </div>
            );
          })}
        </Card>
      )}

      {/* 时间线 */}
      <Card size="small" title="事件时间线">
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #f0f0f0' }}>
              <th style={{ padding: '6px 8px', textAlign: 'left' }}>阶段</th>
              <th style={{ padding: '6px 8px', textAlign: 'right' }}>时间戳</th>
              <th style={{ padding: '6px 8px', textAlign: 'right' }}>相对起始</th>
            </tr>
          </thead>
          <tbody>
            {stageEntries.map(([key, ts], idx) => {
              const relative = idx > 0 && stageEntries[0] ? ts - stageEntries[0][1] : 0;
              return (
                <tr key={key} style={{ borderBottom: '1px solid #f5f5f5' }}>
                  <td style={{ padding: '6px 8px' }}>
                    <Tag color={stageColors[key] || '#666'} style={{ fontSize: 11 }}>
                      {stageLabels[key] || key}
                    </Tag>
                  </td>
                  <td style={{ padding: '6px 8px', textAlign: 'right', fontSize: 12, color: '#666' }}>
                    {new Date(ts).toLocaleTimeString()}.{String(ts % 1000).padStart(3, '0')}
                  </td>
                  <td style={{ padding: '6px 8px', textAlign: 'right', fontSize: 12 }}>
                    {relative > 0 ? `+${formatDur(relative)}` : '0'}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

export default function TracePage() {
  const [items, setItems] = useState<TraceItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [detailId, setDetailId] = useState<string | null>(null);
  const pageSize = 20;

  const fetchList = async (p: number) => {
    setLoading(true);
    try {
      const data = await listTraces({ limit: pageSize, offset: (p - 1) * pageSize, skip_skip: false });
      setItems(data.items);
      setTotal(data.total);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchList(page); }, [page]);

  if (detailId) {
    return <TraceDetail requestId={detailId} onBack={() => setDetailId(null)} />;
  }

  const columns = [
    {
      title: '请求 ID', dataIndex: 'request_id', key: 'request_id', width: 200,
      render: (v: string) => <Text code copyable style={{ fontSize: 11 }}>{v}</Text>,
    },
    {
      title: '协议', dataIndex: 'protocol', key: 'protocol', width: 80,
      render: (v: string) => <Tag>{v || '-'}</Tag>,
    },
    {
      title: '内容', dataIndex: 'content', key: 'content', ellipsis: true,
      render: (v: string) => v ? <Text ellipsis style={{ maxWidth: 300 }}>{v}</Text> : '-',
    },
    {
      title: '耗时', key: 'duration', width: 100,
      render: (_: any, r: TraceItem) => {
        const stages = r.stages || {};
        const times = Object.values(stages).filter((v): v is number => typeof v === 'number');
        if (times.length < 2) return '-';
        return <Text>{formatDur(Math.max(...times) - Math.min(...times))}</Text>;
      },
    },
    {
      title: '阶段数', key: 'stages', width: 70,
      render: (_: any, r: TraceItem) => Object.keys(r.stages || {}).length,
    },
    {
      title: 'SKIP', dataIndex: 'reply_skip', key: 'reply_skip', width: 60,
      render: (v: boolean) => v ? <Tag color="orange">SKIP</Tag> : null,
    },
    {
      title: '时间', dataIndex: 'created_at', key: 'created_at', width: 170,
      render: (v: string) => v.replace('T', ' ').slice(0, 19),
    },
    {
      title: '操作', key: 'actions', width: 70,
      render: (_: any, r: TraceItem) => (
        <Button type="link" size="small" onClick={() => setDetailId(r.request_id)}>详情</Button>
      ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Text type="secondary">共 {total} 条追踪记录</Text>
      </div>
      <Table
        dataSource={items}
        columns={columns}
        rowKey="id"
        loading={loading}
        size="small"
        pagination={{
          current: page,
          pageSize,
          total,
          onChange: setPage,
          showSizeChanger: false,
        }}
      />
    </div>
  );
}
