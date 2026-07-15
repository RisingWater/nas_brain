import { useEffect, useState, useCallback, useRef } from 'react';
import {
  Table, Button, Tag, Card, Row, Col, Space, message, Typography, Switch,
} from 'antd';
import {
  PlayCircleOutlined, StopOutlined, ReloadOutlined, RestOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { listServices, startService, stopService, restartService, enableService } from '../api/services';
import type { ServiceInfo } from '../types/service';

const { Title, Text } = Typography;
const POLL_INTERVAL = 3000;

export default function ServiceManager() {
  const [services, setServices] = useState<ServiceInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [operating, setOperating] = useState<string | null>(null);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const polling = useRef<ReturnType<typeof setInterval>>();

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  const fetchServices = useCallback(async () => {
    try {
      const res = await listServices();
      setServices(res.data);
    } catch {
      // ignore poll errors
    }
  }, []);

  useEffect(() => {
    fetchServices();
    polling.current = setInterval(fetchServices, POLL_INTERVAL);
    return () => clearInterval(polling.current);
  }, [fetchServices]);

  const withOp = (name: string, fn: () => Promise<any>) => {
    setOperating(name);
    fn().finally(() => setOperating(null));
  };

  const handleStart = async (name: string) => {
    try {
      const res = await startService(name);
      message.success(res.message);
      await fetchServices();
    } catch {
      message.error(`启动 ${name} 失败`);
    }
  };

  const handleStop = async (name: string) => {
    try {
      const res = await stopService(name);
      message.success(res.message);
      await fetchServices();
    } catch {
      message.error(`停止 ${name} 失败`);
    }
  };

  const handleRestart = async (name: string) => {
    try {
      const res = await restartService(name);
      message.success(res.message);
      await fetchServices();
    } catch {
      message.error(`重启 ${name} 失败`);
    }
  };

  const handleEnable = async (name: string, enable: boolean) => {
    try {
      const res = await enableService(name, enable);
      message.success(res.message);
      await fetchServices();
    } catch {
      message.error(`${enable ? '启用' : '禁用'} ${name} 失败`);
    }
  };

  const statusTag = (status: string) => {
    if (status === 'disabled') return <Tag color="default">已禁用</Tag>;
    if (status === 'running') return <Tag color="green">运行中</Tag>;
    if (status === 'stopped') return <Tag color="default">已停止</Tag>;
    return <Tag color="orange">{status}</Tag>;
  };

  const columns: ColumnsType<ServiceInfo> = [
    { title: '名称', dataIndex: 'name', key: 'name', width: 120 },
    { title: '启用', key: 'enable', width: 60, align: 'center',
      render: (_, r) => (
        <Switch size="small" checked={r.enable} disabled={operating === r.name}
          onChange={(v) => withOp(r.name, () => handleEnable(r.name, v))} />
      ),
    },
    { title: '描述', dataIndex: 'description', key: 'description', width: 140, responsive: ['md' as const] },
    {
      title: '命令', dataIndex: 'command', key: 'command', responsive: ['lg' as const],
      render: (cmd: string) => <Text copyable style={{ fontSize: 12 }}>{cmd}</Text>,
    },
    { title: '状态', dataIndex: 'status', key: 'status', width: 80, render: statusTag },
    { title: 'PID', dataIndex: 'pid', key: 'pid', width: 80, responsive: ['sm' as const],
      render: (pid: number | null) => pid ?? '-' },
    {
      title: '操作', key: 'action', width: 180,
      render: (_, record) => (
        <Space>
          {record.status === 'running' ? (
            <Button size="small" danger icon={<StopOutlined />}
              loading={operating === record.name}
              onClick={() => withOp(record.name, () => handleStop(record.name))}
            >{isMobile ? '' : '停止'}</Button>
          ) : record.status !== 'disabled' && (
            <Button size="small" type="primary" icon={<PlayCircleOutlined />}
              loading={operating === record.name}
              onClick={() => withOp(record.name, () => handleStart(record.name))}
            >{isMobile ? '' : '启动'}</Button>
          )}
          {record.status !== 'disabled' && (
            <Button size="small" icon={<RestOutlined />}
              loading={operating === record.name}
              onClick={() => withOp(record.name, () => handleRestart(record.name))}
            >{isMobile ? '' : '重启'}</Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <>
      <div style={{ textAlign: 'right', marginBottom: 16 }}>
        <Button icon={<ReloadOutlined />} onClick={fetchServices}>刷新</Button>
      </div>

      {isMobile ? (
        <Row gutter={[8, 8]}>
          {services.map((svc) => (
            <Col span={24} key={svc.name}>
              <Card
                size="small"
                actions={[
                  svc.status === 'running'
                    ? <StopOutlined key="stop" onClick={() => withOp(svc.name, () => handleStop(svc.name))} style={{ color: '#ff4d4f' }} />
                    : <PlayCircleOutlined key="start" onClick={() => withOp(svc.name, () => handleStart(svc.name))} style={{ color: '#52c41a' }} />,
                  <RestOutlined key="restart" onClick={() => withOp(svc.name, () => handleRestart(svc.name))} />,
                ]}
              >
                <Row justify="space-between" align="middle">
                  <Col><Text strong>{svc.name}</Text></Col>
                  <Col><Space>
                    <Switch size="small" checked={svc.enable}
                      disabled={operating === svc.name}
                      onChange={(v) => withOp(svc.name, () => handleEnable(svc.name, v))} />
                    {statusTag(svc.status)}
                  </Space></Col>
                </Row>
                <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                  {svc.description || svc.command}
                </div>
                {svc.pid && <div style={{ fontSize: 12, color: '#aaa' }}>PID: {svc.pid}</div>}
              </Card>
            </Col>
          ))}
        </Row>
      ) : (
        <Table
          columns={columns}
          dataSource={services}
          rowKey="name"
          loading={loading}
          scroll={{ x: 'max-content' }}
          pagination={false}
        />
      )}
    </>
  );
}
