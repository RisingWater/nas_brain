import { useEffect, useState } from 'react';
import { Row, Col, Card, Statistic, Spin, Typography, Button, Divider } from 'antd';
import {
  DatabaseOutlined, SoundOutlined, FileTextOutlined,
  RobotOutlined, ClockCircleOutlined, ThunderboltOutlined,
  PieChartOutlined, BarChartOutlined,
} from '@ant-design/icons';
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend,
} from 'recharts';
import { getDashboardStats } from '../api/dashboard';
import type { DashboardStats } from '../api/dashboard';

const { Text, Title } = Typography;

const STORAGE_PIE_COLORS = ['#1677ff', '#52c41a', '#faad14', '#ff4d4f', '#e8e8e8'];
const MEM_PIE_COLORS = ['#722ed1', '#13c2c2', '#eb2f96', '#fa8c16', '#2f54eb', '#a0d911', '#1890ff', '#fa541c', '#e8e8e8'];
const CPU_COLORS = ['#ff4d4f', '#e8e8e8'];

function formatSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return (bytes / Math.pow(k, i)).toFixed(1) + ' ' + sizes[i];
}

function formatKB(kb: number): string {
  if (kb < 1024) return `${kb} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

function fmtDate(d: string) {
  return `${d.slice(5, 7)}/${d.slice(8, 10)}`;
}

const MEM_LIMIT_KB = 8 * 1024 * 1024;  // 8GB
const STORAGE_LIMIT = 100 * 1024 * 1024 * 1024;  // 100GB

const serviceLabels: Record<string, string> = {
  service_manager: '服务管理', web_services: 'Web服务', db_services: '数据库',
  wechat_gateway: '微信网关', brain_services: '大脑', playback_services: 'TTS',
  schedule_services: '定时任务', voice_gateway: '语音网关',
};

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchStats = async () => {
    setLoading(true);
    try {
      const data = await getDashboardStats();
      setStats(data);
    } catch { /* keep */ }
    finally { setLoading(false); }
  };

  useEffect(() => {
    fetchStats();
    const timer = setInterval(fetchStats, 10000);
    return () => clearInterval(timer);
  }, []);

  if (loading && !stats) {
    return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>;
  }

  const s = stats!;
  const dailyData = [...(s.daily || [])].reverse();

  // 存储饼图
  const usedStorage = s.storage.db_size + s.storage.audio_size + s.storage.tts_cache_size + s.storage.log_size;
  const storageLimit = s.storage.limit || STORAGE_LIMIT;
  const storageRemaining = Math.max(0, storageLimit - usedStorage);
  const storageData = [
    { name: '数据库', value: s.storage.db_size },
    { name: '录音', value: s.storage.audio_size },
    { name: 'TTS缓存', value: s.storage.tts_cache_size },
    { name: '日志', value: s.storage.log_size },
    { name: '剩余', value: storageRemaining },
  ];
  const storageTotal = storageData.reduce((a, b) => a + b.value, 0);

  // 内存饼图
  const memTotal = s.system.memory_total_kb || MEM_LIMIT_KB;
  const usedMem = Object.values(s.system.memory_services || {}).reduce((a, b) => a + b, 0);
  const memRemaining = Math.max(0, memTotal - usedMem);
  const memData = [
    ...Object.entries(s.system.memory_services || {})
      .filter(([, v]) => v > 0)
      .map(([k, v]) => ({ name: serviceLabels[k] || k, value: v })),
    { name: '剩余', value: memRemaining },
  ];

  // CPU 饼图
  const cpuPct = s.system.cpu.pct || 0;
  const cpuData = [
    { name: '使用', value: cpuPct },
    { name: '空闲', value: Math.max(0, 100 - cpuPct) },
  ];

  // 存储明细
  const storageDetail = [
    { label: '数据库', size: s.storage.db_size, color: STORAGE_PIE_COLORS[0] },
    { label: '录音', size: s.storage.audio_size, color: STORAGE_PIE_COLORS[1] },
    { label: 'TTS缓存', size: s.storage.tts_cache_size, color: STORAGE_PIE_COLORS[2] },
    { label: '日志', size: s.storage.log_size, color: STORAGE_PIE_COLORS[3] },
  ].filter(d => d.size > 0);

  // 内存明细
  const memDetail = Object.entries(s.system.memory_services || {})
    .filter(([, v]) => v > 0)
    .map(([k, v], i) => ({ label: serviceLabels[k] || k, size: v, color: MEM_PIE_COLORS[i % MEM_PIE_COLORS.length] }));

  const hasDailyData = dailyData.length > 0;

  return (
    <div>
      <div style={{ textAlign: 'right', marginBottom: 8 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>每10秒自动刷新</Text>
      </div>

      {/* ===== 三个饼图一行 ===== */}
      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        {/* 存储饼图 */}
        <Col xs={24} md={8}>
          <Card size="small" title={<span><PieChartOutlined /> 存储</span>}>
            <div style={{ textAlign: 'center' }}>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={storageData} dataKey="value" cx="50%" cy="50%"
                    outerRadius={80} innerRadius={35}>
                    {storageData.map((_, idx) => (
                      <Cell key={idx} fill={STORAGE_PIE_COLORS[idx % STORAGE_PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v: number) => formatSize(v)} />
                </PieChart>
              </ResponsiveContainer>
              <Text strong style={{ fontSize: 20 }}>{formatSize(usedStorage)}</Text>
              <Text type="secondary"> / {formatSize(storageLimit)}</Text>
            </div>
            <Divider style={{ margin: '8px 0' }} />
            {storageDetail.map(d => (
              <div key={d.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0', fontSize: 13 }}>
                <span><span style={{ color: d.color, marginRight: 6 }}>●</span>{d.label}</span>
                <span>{formatSize(d.size)}</span>
              </div>
            ))}
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0', fontSize: 13, color: '#999' }}>
              <span>剩余</span>
              <span>{formatSize(storageRemaining)}</span>
            </div>
          </Card>
        </Col>

        {/* 内存饼图 */}
        <Col xs={24} md={8}>
          <Card size="small" title={<span><PieChartOutlined /> 内存</span>}>
            <div style={{ textAlign: 'center' }}>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={memData} dataKey="value" cx="50%" cy="50%"
                    outerRadius={80} innerRadius={35}>
                    {memData.map((_, idx) => (
                      <Cell key={idx} fill={MEM_PIE_COLORS[idx % MEM_PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v: number) => formatKB(v)} />
                </PieChart>
              </ResponsiveContainer>
              <Text strong style={{ fontSize: 20 }}>{formatKB(usedMem)}</Text>
              <Text type="secondary"> / {formatKB(memTotal)}</Text>
            </div>
            <Divider style={{ margin: '8px 0' }} />
            {memDetail.map(d => (
              <div key={d.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0', fontSize: 13 }}>
                <span><span style={{ color: d.color, marginRight: 6 }}>●</span>{d.label}</span>
                <span>{formatKB(d.size)}</span>
              </div>
            ))}
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0', fontSize: 13, color: '#999' }}>
              <span>剩余</span>
              <span>{formatKB(memRemaining)}</span>
            </div>
          </Card>
        </Col>

        {/* CPU 饼图 */}
        <Col xs={24} md={8}>
          <Card size="small" title={<span><ThunderboltOutlined /> CPU</span>}>
            <div style={{ textAlign: 'center' }}>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={cpuData} dataKey="value" cx="50%" cy="50%"
                    outerRadius={80} innerRadius={50}>
                    <Cell fill="#ff4d4f" />
                    <Cell fill="#e8e8e8" />
                  </Pie>
                  <Tooltip formatter={(v: number) => `${v}%`} />
                </PieChart>
              </ResponsiveContainer>
              <Text strong style={{ fontSize: 24, color: cpuPct > 80 ? '#ff4d4f' : '#52c41a' }}>
                {cpuPct}%
              </Text>
            </div>
            <Divider style={{ margin: '8px 0' }} />
            <div style={{ fontSize: 13 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0' }}>
                <span>核数</span><span>{s.system.cpu.cores} 核</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0' }}>
                <span>Load 1m</span><span>{s.system.cpu.load_1m.toFixed(2)}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0' }}>
                <span>Load 5m</span><span>{s.system.cpu.load_5m.toFixed(2)}</span>
              </div>
            </div>
          </Card>
        </Col>
      </Row>

      {/* ===== 活跃用户 + Brain运行 ===== */}
      <Row gutter={12} style={{ marginBottom: 16 }}>
        <Col xs={8} sm={6} md={4}>
          <Card size="small"><Statistic title="5分钟活跃" value={s.active_users["5min"]} valueStyle={{ fontSize: 22 }} /></Card>
        </Col>
        <Col xs={8} sm={6} md={4}>
          <Card size="small"><Statistic title="1小时活跃" value={s.active_users["1hour"]} valueStyle={{ fontSize: 22 }} /></Card>
        </Col>
        <Col xs={8} sm={6} md={4}>
          <Card size="small"><Statistic title="24小时活跃" value={s.active_users["1day"]} valueStyle={{ fontSize: 22 }} /></Card>
        </Col>
        <Col xs={12} sm={6} md={4}>
          <Card size="small" hoverable onClick={() => window.location.href = '/traces'}>
            <Statistic title="Brain运行" value={s.brain.uptime_seconds} valueStyle={{ fontSize: 18 }}
              prefix={<ClockCircleOutlined />}
              formatter={(v) => { const sec = Number(v); return `${Math.floor(sec/86400)}天${Math.floor((sec%86400)/3600)}时${Math.floor((sec%3600)/60)}分`; }} />
            <div style={{ fontSize: 11, color: '#999' }}>点击查看请求详情</div>
          </Card>
        </Col>
      </Row>

      {/* ===== Token 用量 ===== */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8, justifyContent: 'space-between' }}>
          <Title level={5} style={{ margin: 0 }}><RobotOutlined /> Token 用量</Title>
          <Button type="link" icon={<FileTextOutlined />}
            href="https://www.deepseek.com" target="_blank" style={{ fontSize: 12 }}>
            DeepSeek 定价详情
          </Button>
        </div>
        <Row gutter={12}>
          <Col xs={12} sm={6} md={4}>
            <Card size="small"><Statistic title="Prompt" value={s.brain.prompt_tokens.toLocaleString()} valueStyle={{ fontSize: 20 }} /></Card>
          </Col>
          <Col xs={12} sm={6} md={4}>
            <Card size="small"><Statistic title="Completion" value={s.brain.completion_tokens.toLocaleString()} valueStyle={{ fontSize: 20 }} /></Card>
          </Col>
          <Col xs={12} sm={6} md={4}>
            <Card size="small"><Statistic title="总计" value={s.brain.total_tokens.toLocaleString()} valueStyle={{ fontSize: 20, color: '#1677ff' }} /></Card>
          </Col>
          <Col xs={12} sm={6} md={4}>
            <Card size="small"><Statistic title="总请求" value={s.brain.total_requests} valueStyle={{ fontSize: 20 }} /></Card>
          </Col>
          <Col xs={12} sm={6} md={4}>
            <Card size="small"><Statistic title="有效回答" value={s.brain.total_answers} valueStyle={{ fontSize: 20 }} /></Card>
          </Col>
        </Row>
      </Card>

      {/* ===== 柱状图：每日请求/回答、耗时 ===== */}
      {hasDailyData && (
        <>
          <Row gutter={12} style={{ marginBottom: 16 }}>
            <Col xs={24} lg={14}>
              <Card size="small" title={<span><BarChartOutlined /> 每日请求 / 有效回答</span>}>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={dailyData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" tickFormatter={fmtDate} fontSize={12} />
                    <YAxis allowDecimals={false} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="total" name="总请求" fill="#1677ff" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="answered" name="有效回答" fill="#52c41a" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            </Col>
            <Col xs={24} lg={10}>
              <Card size="small" title={<span><BarChartOutlined /> 每日平均耗时</span>}>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={dailyData.filter(d => d.avg_ms > 0)}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" tickFormatter={fmtDate} fontSize={12} />
                    <YAxis tickFormatter={(v: number) => `${v}ms`} fontSize={12} />
                    <Tooltip formatter={(v: number) => `${v.toFixed(0)}ms`} />
                    <Bar dataKey="avg_ms" name="平均耗时" fill="#722ed1" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </Card>
            </Col>
          </Row>
        </>
      )}

      {/* 无每日数据时的说明 */}
      {!hasDailyData && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <Text type="secondary">以上统计为累计值。发送消息后，每日请求/回答和耗时的柱状图会在这里显示。</Text>
        </Card>
      )}
    </div>
  );
}
