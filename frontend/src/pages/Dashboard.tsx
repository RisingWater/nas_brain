import { useEffect, useState } from 'react';
import { Row, Col, Card, Statistic, Spin, Typography, Button } from 'antd';
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

function fmtDate(d: string) { return `${d.slice(5, 7)}/${d.slice(8, 10)}`; }

const MEM_LIMIT_KB = 8 * 1024 * 1024;
const STORAGE_LIMIT = 100 * 1024 * 1024 * 1024;

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
  // 确保至少有一个占位数据让柱状图显示
  const chartData = dailyData.length > 0 ? dailyData
    : [{ date: new Date().toISOString().slice(0, 10), total: 0, answered: 0, avg_ms: 0, prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 }];

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

  // 内存饼图
  const memTotal = s.system.memory_total_kb || MEM_LIMIT_KB;
  const usedMem = Object.values(s.system.memory_services || {}).reduce((a, b) => a + b, 0);
  const memRemaining = Math.max(0, memTotal - usedMem);
  const memData = [
    ...Object.entries(s.system.memory_services || {}).filter(([, v]) => v > 0).map(([k, v]) => ({ name: serviceLabels[k] || k, value: v })),
    { name: '剩余', value: memRemaining },
  ];

  // CPU
  const cpuPct = s.system.cpu.pct || 0;
  const cpuData = [
    { name: '使用', value: cpuPct },
    { name: '空闲', value: Math.max(0, 100 - cpuPct) },
  ];

  const storageDetail = [
    { label: '数据库', size: s.storage.db_size, color: STORAGE_PIE_COLORS[0] },
    { label: '录音', size: s.storage.audio_size, color: STORAGE_PIE_COLORS[1] },
    { label: 'TTS缓存', size: s.storage.tts_cache_size, color: STORAGE_PIE_COLORS[2] },
    { label: '日志', size: s.storage.log_size, color: STORAGE_PIE_COLORS[3] },
  ].filter(d => d.size > 0);

  const memDetail = Object.entries(s.system.memory_services || {})
    .filter(([, v]) => v > 0)
    .map(([k, v], i) => ({ label: serviceLabels[k] || k, size: v, color: MEM_PIE_COLORS[i % MEM_PIE_COLORS.length] }));

  return (
    <div>
      <div style={{ textAlign: 'right', marginBottom: 8 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>每10秒自动刷新</Text>
      </div>

      {/* ===== 三个饼图一行 ===== */}
      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col xs={24} md={8}>
          <Card size="small" title={<span><PieChartOutlined /> 存储</span>}>
            <div style={{ textAlign: 'center' }}>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={storageData} dataKey="value" cx="50%" cy="50%" outerRadius={80} innerRadius={35}>
                    {storageData.map((_, idx) => (<Cell key={idx} fill={STORAGE_PIE_COLORS[idx % STORAGE_PIE_COLORS.length]} />))}
                  </Pie>
                  <Tooltip formatter={(v: number) => formatSize(v)} />
                </PieChart>
              </ResponsiveContainer>
              <Text strong style={{ fontSize: 20 }}>{formatSize(usedStorage)}</Text>
              <Text type="secondary"> / {formatSize(storageLimit)}</Text>
            </div>
            <div style={{ marginTop: 8 }}>
              {storageDetail.map(d => (
                <div key={d.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0', fontSize: 13 }}>
                  <span><span style={{ color: d.color, marginRight: 6 }}>●</span>{d.label}</span>
                  <span>{formatSize(d.size)}</span>
                </div>
              ))}
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0', fontSize: 13, color: '#999' }}>
                <span>剩余</span><span>{formatSize(storageRemaining)}</span>
              </div>
            </div>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card size="small" title={<span><PieChartOutlined /> 内存</span>}>
            <div style={{ textAlign: 'center' }}>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={memData} dataKey="value" cx="50%" cy="50%" outerRadius={80} innerRadius={35}>
                    {memData.map((_, idx) => (<Cell key={idx} fill={MEM_PIE_COLORS[idx % MEM_PIE_COLORS.length]} />))}
                  </Pie>
                  <Tooltip formatter={(v: number) => formatKB(v)} />
                </PieChart>
              </ResponsiveContainer>
              <Text strong style={{ fontSize: 20 }}>{formatKB(usedMem)}</Text>
              <Text type="secondary"> / {formatKB(memTotal)}</Text>
            </div>
            <div style={{ marginTop: 8 }}>
              {memDetail.map(d => (
                <div key={d.label} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0', fontSize: 13 }}>
                  <span><span style={{ color: d.color, marginRight: 6 }}>●</span>{d.label}</span>
                  <span>{formatKB(d.size)}</span>
                </div>
              ))}
              <div style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0', fontSize: 13, color: '#999' }}>
                <span>剩余</span><span>{formatKB(memRemaining)}</span>
              </div>
            </div>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card size="small" title={<span><ThunderboltOutlined /> CPU</span>}>
            <div style={{ textAlign: 'center' }}>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie data={cpuData} dataKey="value" cx="50%" cy="50%" outerRadius={80} innerRadius={50}>
                    <Cell fill="#ff4d4f" /><Cell fill="#e8e8e8" />
                  </Pie>
                  <Tooltip formatter={(v: number) => `${v}%`} />
                </PieChart>
              </ResponsiveContainer>
              <Text strong style={{ fontSize: 24, color: cpuPct > 80 ? '#ff4d4f' : '#52c41a' }}>{cpuPct}%</Text>
            </div>
            <div style={{ marginTop: 8, fontSize: 13 }}>
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

      {/* ===== 两个卡片一行 ===== */}
      <Row gutter={12} style={{ marginBottom: 16 }}>
        <Col xs={12} md={6}>
          <Card size="small" hoverable onClick={() => window.location.href = '/traces'}>
            <Statistic title="Brain 运行时间" value={s.brain.uptime_seconds} valueStyle={{ fontSize: 20 }}
              prefix={<ClockCircleOutlined />}
              formatter={(v) => {
                const sec = Number(v);
                return `${Math.floor(sec / 86400)}天${Math.floor((sec % 86400) / 3600)}时${Math.floor((sec % 3600) / 60)}分`;
              }} />
            <div style={{ fontSize: 11, color: '#999', marginTop: 4 }}>点击查看请求详情 →</div>
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card size="small">
            <Statistic title="Token 总用量" value={s.brain.total_tokens.toLocaleString()} valueStyle={{ fontSize: 20, color: '#1677ff' }}
              prefix={<RobotOutlined />} />
            <Button type="link" icon={<FileTextOutlined />}
              href="https://www.deepseek.com" target="_blank" style={{ padding: 0, fontSize: 12, marginTop: 2 }}>
              DeepSeek 定价详情 →
            </Button>
          </Card>
        </Col>
      </Row>

      {/* ===== 三个柱状图 ===== */}
      <Row gutter={12} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={8}>
          <Card size="small" title={<span><BarChartOutlined /> 每日请求 / 回答</span>}>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tickFormatter={fmtDate} fontSize={11} />
                <YAxis allowDecimals={false} domain={[0, 'auto']} />
                <Tooltip />
                <Legend />
                <Bar dataKey="total" name="总请求" fill="#1677ff" radius={[4, 4, 0, 0]} />
                <Bar dataKey="answered" name="有效回答" fill="#52c41a" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card size="small" title={<span><BarChartOutlined /> 每日 Token 消耗</span>}>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tickFormatter={fmtDate} fontSize={11} />
                <YAxis domain={[0, 'auto']} />
                <Tooltip />
                <Legend />
                <Bar dataKey="total_tokens" name="Total Tokens" fill="#722ed1" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </Col>
        <Col xs={24} lg={8}>
          <Card size="small" title={<span><BarChartOutlined /> 每日平均耗时</span>}>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tickFormatter={fmtDate} fontSize={11} />
                <YAxis tickFormatter={(v: number) => `${v}ms`} fontSize={11} domain={[0, 'auto']} />
                <Tooltip formatter={(v: number) => `${v.toFixed(0)}ms`} />
                <Legend />
                <Bar dataKey="avg_ms" name="平均耗时" fill="#fa8c16" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </Card>
        </Col>
      </Row>
    </div>
  );
}
