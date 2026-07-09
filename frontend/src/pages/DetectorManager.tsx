import { useEffect, useState, useCallback } from 'react';
import {
  Card, Table, Button, Row, Col, Typography, Space, Tag, message,
} from 'antd';
import { ReloadOutlined, ApiOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { listDetectors, reloadDetectors } from '../api/detectors';
import type { DetectorInfo } from '../types/detector';

const { Title, Text } = Typography;

export default function DetectorManager() {
  const [detectors, setDetectors] = useState<DetectorInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [reloading, setReloading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listDetectors();
      setDetectors(res.data);
    } catch {
      message.error('获取任务列表失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleReload = async () => {
    setReloading(true);
    try {
      const res = await reloadDetectors();
      message.success(`重载完成: ${res.data.total} 个任务`);
      await fetchData();
    } catch {
      message.error('重载失败');
    } finally {
      setReloading(false);
    }
  };

  const formatInterval = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}min`;
    return `${Math.floor(seconds / 3600)}h`;
  };

  const columns: ColumnsType<DetectorInfo> = [
    { title: '名称', dataIndex: 'name', key: 'name', width: 120,
      render: (name: string) => <Text code>{name}</Text>,
    },
    { title: '实现类', dataIndex: 'class', key: 'class', width: 180,
      render: (v: string) => <Text type="secondary">{v}</Text>,
    },
    {
      title: '运行间隔', dataIndex: 'interval', key: 'interval', width: 100,
      render: (v: number) => <Tag>{formatInterval(v)}</Tag>,
    },
    {
      title: '状态', key: 'status', width: 100,
      render: () => <Tag color="processing">活跃</Tag>,
    },
  ];

  return (
    <>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={4} style={{ margin: 0 }}>
            <ApiOutlined /> 定时任务管理
          </Title>
          <Text type="secondary" style={{ fontSize: 12 }}>已加载 {detectors.length} 个任务</Text>
        </Col>
        <Col>
          <Button icon={<ReloadOutlined />} loading={reloading} onClick={handleReload}>
            热重载
          </Button>
        </Col>
      </Row>

      <Table
        columns={columns}
        dataSource={detectors}
        rowKey="name"
        loading={loading}
        scroll={{ x: 'max-content' }}
        pagination={false}
        size="small"
      />
    </>
  );
}
