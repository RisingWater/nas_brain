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

const STORAGE_COLORS = ['#1677ff', '#52c41a', '#faad14', '#ff4d4f'];
const MEM_COLORS = ['#722ed1', '#13c2c2', '#eb2f96', '#fa8c16', '#2f54eb', '#a0d911', '#1890ff', '#fa541c'];

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

const serviceLabels: Record<string, string> = {
  service_manager: '服务管理', web_services: 'Web服务', db_services: '数据库',
  wechat_gateway: '微信网关', brain_services: '大脑', playback_services: 'TTS',
  schedule_services: '定时任务', voice_gateway: '语音网关',
};

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [dailyData, setDailyData] = useState<{ date: string; total: number; answered: number; avg_ms: number }[]>([]);

  const fetchStats = async () => {
    setLoading(true);
    try {
      const data = await getDashboardStats();
      setStats(data);
      setDailyData([...(data.daily || [])].reverse());
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

  const storageData = [
    { name: '数据库', value: s.storage.db_size },
    { name: '录音', value: s.storage.audio_size },
    { name: 'TTS缓存', value: s.storage.tts_cache_size },
    { name: '日志', value: s.storage.log_size },
  ].filter(d => d.value > 0);
  const totalStorage = storageData.reduce((a, b) => a + b.value, 0);
  const storagePct = s.storage.limit > 0 ? (totalStorage / s.storage.limit * 100).toFixed(1) : 0;

  const memData = Object.entries(s.system.memory_services || {})
    .filter(([, v]) => v > 0)
    .map(([k, v]) => ({ name: serviceLabels[k] || k, value: v }));
  const totalMem = memData.reduce((a, b) => a + b.value, 0);

  return (
    <div>
      <div style={{ textAlign: 'right', marginBottom: 8 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>每10秒自动刷新</Text>
      </div>

      {/* 存储饼图 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12 }}>
          <PieChartOutlined style={{ fontSize: 18, marginRight: 8 }} />
          <Title level={5} style={{ margin: 0 }}>存储 {formatSize(totalStorage)} / 100 GB ({storagePct}%)</Title>
        </div>
        <Row gutter={24} align="middle">
          <Col xs={24} sm={10} md={8}>
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={storageData} dataKey="value" nameKey="name" cx="50%" cy="50%"
                  outerRadius={90} innerRadius={40}>
                  {storageData.map((_, idx) => (
                    <Cell key={idx} fill={STORAGE_COLORS[idx % STORAGE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v: number) => formatSize(v)} />
              </PieChart>
            </ResponsiveContainer>
          </Col>
          <Col xs={24} sm={14} md={16}>
            <Row gutter={[8, 4]}>
              {storageData.map((d, i) => (
                <Col span={12} key={d.name}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '2px 0' }}>
                    <div style={{
                      width: 10, height: 10, borderRadius: 2,
                      background: STORAGE_COLORS[i % STORAGE_COLORS.length], flexShrink: 0,
                    }} />
                    <Text style={{ fontSize: 13, flex: 1 }}>{d.name}</Text>
                    <Text strong style={{ fontSize: 13 }}>{formatSize(d.value)}</Text>
                  </div>
                </Col>
              ))}
            </Row>
          </Col>
        </Row>
      </Card>

      {/* 内存饼图 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12 }}>
          <PieChartOutlined style={{ fontSize: 18, marginRight: 8 }} />
          <Title level={5} style={{ margin: 0 }}>服务内存 {formatKB(totalMem)}</Title>
        </div>
        <Row gutter={24} align="middle">
          <Col xs={24} sm={10} md={8}>
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={memData} dataKey="value" nameKey="name" cx="50%" cy="50%"
                  outerRadius={90} innerRadius={40}>
                  {memData.map((_, idx) => (
                    <Cell key={idx} fill={MEM_COLORS[idx % MEM_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v: number) => formatKB(v)} />
              </PieChart>
            </ResponsiveContainer>
          </Col>
          <Col xs={24} sm={14} md={16}>
            <Row gutter={[8, 4]}>
              {memData.map((d, i) => (
                <Col span={12} key={d.name}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '2px 0' }}>
                    <div style={{
                      width: 10, height: 10, borderRadius: 2,
                      background: MEM_COLORS[i % MEM_COLORS.length], flexShrink: 0,
                    }} />
                    <Text style={{ fontSize: 13, flex: 1 }}>{d.name}</Text>
                    <Text strong style={{ fontSize: 13 }}>{formatKB(d.value)}</Text>
                  </div>
                </Col>
              ))}
            </Row>
          </Col>
        </Row>
      </Card>

      {/* CPU + 活跃用户 */}
      <Row gutter={12} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={6} md={4}>
          <Card size="small"><Statistic title="CPU 1m" value={s.system.cpu.load_1m} precision={2}
            prefix={<ThunderboltOutlined />} valueStyle={{ fontSize: 22 }} /></Card>
        </Col>
        <Col xs={12} sm={6} md={4}>
          <Card size="small"><Statistic title="CPU 5m" value={s.system.cpu.load_5m} precision={2}
            valueStyle={{ fontSize: 22 }} /></Card>
        </Col>
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

      {/* 每日请求/回答 */}
      {dailyData.length > 0 && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
            <BarChartOutlined style={{ fontSize: 18, marginRight: 8 }} />
            <Title level={5} style={{ margin: 0 }}>每日请求 / 有效回答</Title>
          </div>
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
      )}

      {/* Token 统计 */}
      {s.brain.total_tokens > 0 && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8, justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center' }}>
              <BarChartOutlined style={{ fontSize: 18, marginRight: 8 }} />
              <Title level={5} style={{ margin: 0 }}>Token 用量</Title>
            </div>
            <Button type="link" icon={<FileTextOutlined />}
              href="https://www.deepseek.com" target="_blank" style={{ fontSize: 12 }}>
              DeepSeek 定价详情
            </Button>
          </div>
          <Row gutter={16}>
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
      )}

      {/* 每日平均耗时 */}
      {dailyData.filter(d => d.avg_ms > 0).length > 0 && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
            <BarChartOutlined style={{ fontSize: 18, marginRight: 8 }} />
            <Title level={5} style={{ margin: 0 }}>每日平均应答耗时</Title>
          </div>
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
      )}
    </div>
  );
}
