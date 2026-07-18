import { useEffect, useState } from 'react';
import { Row, Col, Card, Statistic, Spin, Typography, Table, Tag, Divider } from 'antd';
import {
  DatabaseOutlined, SoundOutlined, FileTextOutlined,
  ThunderboltOutlined, RobotOutlined, TeamOutlined,
  ClockCircleOutlined, CloudServerOutlined,
} from '@ant-design/icons';
import { getDashboardStats } from '../api/dashboard';
import type { DashboardStats } from '../api/dashboard';

const { Text, Title } = Typography;

function formatSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return (bytes / Math.pow(k, i)).toFixed(1) + ' ' + sizes[i];
}

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  const parts: string[] = [];
  if (d > 0) parts.push(`${d}天`);
  if (h > 0) parts.push(`${h}时`);
  if (m > 0) parts.push(`${m}分`);
  if (s > 0 || parts.length === 0) parts.push(`${s}秒`);
  return parts.join('');
}

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchStats = async () => {
    setLoading(true);
    try {
      const data = await getDashboardStats();
      setStats(data);
    } catch {
      // keep old data if any
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
    const timer = setInterval(fetchStats, 10000); // 每10秒刷新
    return () => clearInterval(timer);
  }, []);

  if (loading && !stats) {
    return (
      <div style={{ textAlign: 'center', padding: 80 }}>
        <Spin size="large" />
        <div style={{ marginTop: 16 }}><Text type="secondary">加载中...</Text></div>
      </div>
    );
  }

  const s = stats!;

  const audioColumns = [
    { title: '用户', dataIndex: 'user_id', key: 'user_id', render: (v: string) => <Text code>{v}</Text> },
    { title: '文件数', dataIndex: 'count', key: 'count' },
    { title: '大小', dataIndex: 'size', key: 'size', render: (v: number) => formatSize(v) },
  ];

  return (
    <div>
      {/* 自动刷新提示 */}
      <div style={{ textAlign: 'right', marginBottom: 12 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>每10秒自动刷新</Text>
      </div>

      {/* 系统资源 */}
      <Title level={5}><CloudServerOutlined /> 系统资源</Title>
      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={8} md={4}>
          <Card size="small">
            <Statistic
              title="内存"
              value={s.system.memory_mb}
              suffix="MB"
              valueStyle={{ fontSize: 22 }}
              prefix={<ThunderboltOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card size="small">
            <Statistic
              title="CPU (1m)"
              value={s.system.load_1m}
              precision={2}
              valueStyle={{ fontSize: 22 }}
              prefix={<CloudServerOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card size="small">
            <Statistic
              title="CPU (5m)"
              value={s.system.load_5m}
              precision={2}
              valueStyle={{ fontSize: 22 }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card size="small">
            <Statistic
              title="Brain 运行"
              value={formatUptime(s.brain.uptime_seconds)}
              valueStyle={{ fontSize: 18 }}
              prefix={<ClockCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {/* 存储 */}
      <Title level={5}><DatabaseOutlined /> 存储</Title>
      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={8} md={4}>
          <Card size="small">
            <Statistic
              title="数据库"
              value={formatSize(s.storage.db.size)}
              valueStyle={{ fontSize: 20 }}
              prefix={<DatabaseOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card size="small">
            <Statistic
              title="录音"
              value={formatSize(s.storage.audio.total_size)}
              valueStyle={{ fontSize: 20 }}
              prefix={<SoundOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card size="small">
            <Statistic
              title="TTS 缓存"
              value={formatSize(s.storage.tts_cache_size)}
              valueStyle={{ fontSize: 20 }}
              prefix={<FileTextOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card size="small">
            <Statistic
              title="日志"
              value={formatSize(s.storage.log_size)}
              valueStyle={{ fontSize: 20 }}
              prefix={<FileTextOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {/* 对话统计 */}
      <Title level={5}><RobotOutlined /> 对话统计</Title>
      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={8} md={4}>
          <Card size="small">
            <Statistic
              title="总请求"
              value={s.brain.total_requests}
              valueStyle={{ fontSize: 22 }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card size="small">
            <Statistic
              title="有效回答"
              value={s.brain.total_answers}
              valueStyle={{ fontSize: 22 }}
              prefix={<RobotOutlined />}
            />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card size="small">
            <Statistic
              title="Prompt Tokens"
              value={s.brain.prompt_tokens.toLocaleString()}
              valueStyle={{ fontSize: 18 }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card size="small">
            <Statistic
              title="Completion Tokens"
              value={s.brain.completion_tokens.toLocaleString()}
              valueStyle={{ fontSize: 18 }}
            />
          </Card>
        </Col>
        <Col xs={12} sm={8} md={4}>
          <Card size="small">
            <Statistic
              title="总 Tokens"
              value={s.brain.total_tokens.toLocaleString()}
              valueStyle={{ fontSize: 20, color: '#1677ff' }}
            />
          </Card>
        </Col>
      </Row>

      {/* 活跃用户 */}
      <Title level={5}><TeamOutlined /> 活跃用户</Title>
      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col xs={8} sm={6} md={4}>
          <Card size="small">
            <Statistic title="5分钟内" value={s.active_users["5min"]} valueStyle={{ fontSize: 22 }} />
          </Card>
        </Col>
        <Col xs={8} sm={6} md={4}>
          <Card size="small">
            <Statistic title="1小时内" value={s.active_users["1hour"]} valueStyle={{ fontSize: 22 }} />
          </Card>
        </Col>
        <Col xs={8} sm={6} md={4}>
          <Card size="small">
            <Statistic title="24小时内" value={s.active_users["1day"]} valueStyle={{ fontSize: 22 }} />
          </Card>
        </Col>
      </Row>

      {/* 各用户录音详表 */}
      {s.storage.audio.users.length > 0 && (
        <>
          <Divider />
          <Title level={5}><SoundOutlined /> 各用户录音分布</Title>
          <Table
            dataSource={s.storage.audio.users}
            columns={audioColumns}
            rowKey="user_id"
            size="small"
            pagination={false}
          />
        </>
      )}
    </div>
  );
}
