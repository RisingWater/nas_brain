import { useEffect, useState, useRef } from 'react';
import {
  Table, Button, Slider, InputNumber, Typography, Tag, Space, message,
  Row, Col, Select, Popconfirm, Tabs, Tooltip,
} from 'antd';
import {
  CheckOutlined, CloseOutlined, QuestionOutlined,
  PlayCircleOutlined, DeleteOutlined, DownloadOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import {
  getThreshold, setThreshold, listRecords, updateCategory, deleteRecord, getAudioUrl,
  getFrameSamples, setFrameSamples, getVadSilence, setVadSilence,
  getDebugThreshold, setDebugThreshold,
  listDebugAudio, getDebugAudioUrl, classifyDebugAudio, deleteDebugAudio, getPackageUrl,
} from '../api/wakeword';
import type { WakewordRecord, DebugAudioItem } from '../api/wakeword';

const { Text } = Typography;

const categoryColors: Record<string, string> = {
  positive: 'green', negative: 'red', unclassified: 'default',
};
const categoryLabels: Record<string, string> = {
  positive: 'Positive', negative: 'Negative', unclassified: '未分类',
};

const SLIDER_STYLE: React.CSSProperties = { width: 240 };
const INPUT_STYLE: React.CSSProperties = { width: 80 };
const BTN_STYLE: React.CSSProperties = { width: 100 };

export default function WakewordManager() {
  const [threshold, setThresholdVal] = useState(0.7);
  const [debugThreshold, setDebugThresholdVal] = useState(0.5);
  const [frameSamples, setFrameSamplesVal] = useState(3200);
  const [vadSilence, setVadSilenceVal] = useState(1600);

  // 记录 tab
  const [records, setRecords] = useState<WakewordRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [categoryFilter, setCategoryFilter] = useState<string | undefined>();
  const [playing, setPlaying] = useState<number | null>(null);

  // 调试 tab
  const [debugItems, setDebugItems] = useState<DebugAudioItem[]>([]);
  const [debugLoading, setDebugLoading] = useState(false);
  const [playingDebug, setPlayingDebug] = useState<string | null>(null);

  const audioRef = useRef<HTMLAudioElement>(null);

  // ---- 配置加载 ----
  const loadConfig = async () => {
    try {
      const [t, dt, fs, ms] = await Promise.all([
        getThreshold(), getDebugThreshold(), getFrameSamples(), getVadSilence(),
      ]);
      setThresholdVal(t);
      setDebugThresholdVal(dt);
      setFrameSamplesVal(fs);
      setVadSilenceVal(ms);
    } catch { message.error('加载配置失败'); }
  };

  useEffect(() => { loadConfig(); }, []);

  // ---- 记录 tab ----
  const fetchRecords = async () => {
    setLoading(true);
    try {
      const res = await listRecords({ category: categoryFilter, limit: pageSize, offset: (page - 1) * pageSize });
      setRecords(res.items);
      setTotal(res.total);
    } catch { message.error('加载记录失败'); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchRecords(); }, [page, pageSize, categoryFilter]);

  const handleCat = async (id: number, cat: string) => {
    try { await updateCategory(id, cat); message.success(`已标记为 ${categoryLabels[cat]}`); fetchRecords(); }
    catch { message.error('操作失败'); }
  };

  const handleDel = async (id: number) => {
    try { await deleteRecord(id); message.success('已删除'); fetchRecords(); }
    catch { message.error('删除失败'); }
  };

  const handlePlay = (id: number) => {
    setPlaying(id);
    if (audioRef.current) {
      audioRef.current.src = getAudioUrl(id);
      audioRef.current.play().catch(() => { message.error('播放失败'); setPlaying(null); });
    }
  };

  const formatTime = (t: string) => {
    const d = new Date(t + 'Z');
    return d.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });
  };

  // ---- 调试 tab ----
  const fetchDebug = async () => {
    setDebugLoading(true);
    try { const items = await listDebugAudio(); setDebugItems(items); }
    catch { message.error('加载调试音频失败'); }
    finally { setDebugLoading(false); }
  };

  const handleDebugPlay = (filename: string) => {
    setPlayingDebug(filename);
    if (audioRef.current) {
      audioRef.current.src = getDebugAudioUrl(filename);
      audioRef.current.play().catch(() => { message.error('播放失败'); setPlayingDebug(null); });
    }
  };

  const handleDebugClassify = async (filename: string, cat: string) => {
    try { await classifyDebugAudio(filename, cat); message.success(`已转移到 ${categoryLabels[cat]}`); fetchDebug(); }
    catch { message.error('操作失败'); }
  };

  const handleDebugDel = async (filename: string) => {
    try { await deleteDebugAudio(filename); message.success('已删除'); fetchDebug(); }
    catch { message.error('删除失败'); }
  };

  const onAudioEnd = () => { setPlaying(null); setPlayingDebug(null); };

  // ---- 列定义 ----
  const columns: ColumnsType<WakewordRecord> = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    { title: '唤醒词 ID', dataIndex: 'wakeword_id', key: 'wakeword_id', width: 120 },
    { title: '分数', dataIndex: 'score', key: 'score', width: 80,
      render: (s: number) => <Text strong>{(s * 100).toFixed(1)}%</Text> },
    { title: '分类', dataIndex: 'category', key: 'category', width: 100,
      render: (c: string) => <Tag color={categoryColors[c]}>{categoryLabels[c] || c}</Tag> },
    { title: '音频', key: 'audio', width: 80,
      render: (_, r) => (
        <Button type="link" size="small" icon={<PlayCircleOutlined />}
                loading={playing === r.id} onClick={() => handlePlay(r.id)}>播放</Button>) },
    { title: '操作', key: 'action', width: 300,
      render: (_, r) => (
        <Space size={0}>
          {r.category !== 'positive' && <Button type="link" size="small" icon={<CheckOutlined />} style={{ color: '#52c41a' }} onClick={() => handleCat(r.id, 'positive')}>Positive</Button>}
          {r.category !== 'negative' && <Button type="link" size="small" icon={<CloseOutlined />} style={{ color: '#ff4d4f' }} onClick={() => handleCat(r.id, 'negative')}>Negative</Button>}
          {r.category !== 'unclassified' && <Button type="link" size="small" icon={<QuestionOutlined />} onClick={() => handleCat(r.id, 'unclassified')}>重置</Button>}
          <Popconfirm title="删除？" onConfirm={() => handleDel(r.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>) },
    { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 160,
      render: (t: string) => formatTime(t) },
  ];

  const debugColumns: ColumnsType<DebugAudioItem> = [
    { title: '文件名', dataIndex: 'filename', key: 'filename', width: 200 },
    { title: '分数', dataIndex: 'score', key: 'score', width: 80,
      render: (s: number) => <Text strong>{(s * 100).toFixed(1)}%</Text> },
    { title: '音频', key: 'audio', width: 80,
      render: (_, r) => (
        <Button type="link" size="small" icon={<PlayCircleOutlined />}
                loading={playingDebug === r.filename}
                onClick={() => handleDebugPlay(r.filename)}>播放</Button>) },
    { title: '操作', key: 'action', width: 300,
      render: (_, r) => (
        <Space size={0}>
          <Button type="link" size="small" icon={<CheckOutlined />} style={{ color: '#52c41a' }}
                  onClick={() => handleDebugClassify(r.filename, 'positive')}>Positive</Button>
          <Button type="link" size="small" icon={<CloseOutlined />} style={{ color: '#ff4d4f' }}
                  onClick={() => handleDebugClassify(r.filename, 'negative')}>Negative</Button>
          <Popconfirm title="删除？" onConfirm={() => handleDebugDel(r.filename)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>) },
    { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 160,
      render: (t: string) => t || '-' },
  ];

  // ---- 渲染配置行 ----
  const configRow = (label: string, slider: JSX.Element, input: JSX.Element, btn: JSX.Element, tooltip?: string) => (
    <Row gutter={8} align="middle" style={{ marginBottom: 12 }}>
      <Col style={{ width: 140, textAlign: 'right', paddingRight: 8 }}>
        {tooltip ? <Tooltip title={tooltip}><Text strong>{label}</Text></Tooltip> : <Text strong>{label}</Text>}
      </Col>
      <Col flex="auto" style={{ maxWidth: 260 }}>{slider}</Col>
      <Col style={{ width: 100 }}>{input}</Col>
      <Col style={{ width: 110 }}>{btn}</Col>
    </Row>
  );

  return (
    <div>
      {/* ===== 配置区域 ===== */}
      {configRow('检测阈值',
        <Slider min={0} max={1} step={0.05} value={threshold} onChange={setThresholdVal} style={SLIDER_STYLE} />,
        <InputNumber min={0} max={1} step={0.05} value={threshold} onChange={(v) => setThresholdVal(v || 0.7)} style={INPUT_STYLE} />,
        <Button type="primary" size="small" onClick={async () => { try { await setThreshold(threshold); message.success('已保存'); } catch { message.error('保存失败'); } }} style={BTN_STYLE}>保存</Button>,
      )}
      {configRow('调试阈值',
        <Slider min={0} max={1} step={0.05} value={debugThreshold} onChange={setDebugThresholdVal} style={SLIDER_STYLE} />,
        <InputNumber min={0} max={1} step={0.05} value={debugThreshold} onChange={(v) => setDebugThresholdVal(v || 0.5)} style={INPUT_STYLE} />,
        <Button type="primary" size="small" onClick={async () => { try { await setDebugThreshold(debugThreshold); message.success('调试阈值已保存'); } catch { message.error('保存失败'); } }} style={BTN_STYLE}>保存</Button>,
        '高于此值但低于检测阈值的唤醒词会保存音频供分析',
      )}
      {configRow('帧大小',
        <Slider min={800} max={16000} step={100} value={frameSamples} onChange={setFrameSamplesVal}
                marks={{ 800: '800', 3200: '3200', 8000: '8000', 16000: '16000' }} style={SLIDER_STYLE} />,
        <InputNumber min={800} max={64000} step={100} value={frameSamples} onChange={(v) => setFrameSamplesVal(v || 3200)} style={INPUT_STYLE} />,
        <Button type="primary" size="small" onClick={async () => { try { await setFrameSamples(frameSamples); message.success('帧大小已保存'); } catch { message.error('保存失败'); } }} style={BTN_STYLE}>保存</Button>,
        frameSamples >= 16000 ? '1次/秒' : `${Math.round(16000 / frameSamples)}次/秒`,
      )}
      {configRow('静音判定(ms)',
        <Slider min={200} max={5000} step={100} value={vadSilence} onChange={setVadSilenceVal}
                marks={{ 200: '200', 1600: '1600', 3000: '3000', 5000: '5000' }} style={SLIDER_STYLE} />,
        <InputNumber min={200} max={10000} step={100} value={vadSilence} onChange={(v) => setVadSilenceVal(v || 1600)} style={INPUT_STYLE} />,
        <Button type="primary" size="small" onClick={async () => { try { await setVadSilence(vadSilence); message.success('静音判定已保存'); } catch { message.error('保存失败'); } }} style={BTN_STYLE}>保存</Button>,
      )}

      <audio ref={audioRef} onEnded={onAudioEnd} style={{ display: 'none' }} />

      {/* ===== Tab 区域 ===== */}
      <Tabs items={[
        {
          key: 'records',
          label: '唤醒记录',
          children: (
            <>
              <Row gutter={12} style={{ marginBottom: 12 }}>
                <Col>
                  <Select style={{ width: 140 }} placeholder="全部类型" allowClear value={categoryFilter}
                    onChange={(v) => { setCategoryFilter(v); setPage(1); }}
                    options={[
                      { label: '全部', value: undefined },
                      { label: 'Positive', value: 'positive' },
                      { label: 'Negative', value: 'negative' },
                      { label: '未分类', value: 'unclassified' },
                    ]} />
                </Col>
                <Col><Button onClick={() => { setPage(1); fetchRecords(); }}>刷新</Button></Col>
                <Col flex="auto" style={{ textAlign: 'right' }}>
                  <a href={getPackageUrl()} target="_blank" rel="noreferrer">
                    <Button icon={<DownloadOutlined />}>打包下载（重新训练）</Button>
                  </a>
                </Col>
              </Row>
              <Table columns={columns} dataSource={records} rowKey="id" loading={loading}
                     scroll={{ x: 'max-content' }}
                     pagination={{ current: page, pageSize, total, showSizeChanger: true,
                       showTotal: (t) => `共 ${t} 条`,
                       onChange: (p, ps) => { setPage(p); setPageSize(ps); } }} />
            </>
          ),
        },
        {
          key: 'debug',
          label: '调试音频',
          children: (
            <>
              <Row gutter={12} style={{ marginBottom: 12 }}>
                <Col><Button onClick={() => { fetchDebug(); }} loading={debugLoading}>刷新</Button></Col>
              </Row>
              <Table columns={debugColumns} dataSource={debugItems} rowKey="filename" loading={debugLoading}
                     scroll={{ x: 'max-content' }}
                     pagination={{ pageSize: 20, showSizeChanger: true,
                       showTotal: (t) => `共 ${t} 条` }} />
            </>
          ),
        },
      ]} />
    </div>
  );
}
