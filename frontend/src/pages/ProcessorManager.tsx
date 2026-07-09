import { useEffect, useState, useCallback } from 'react';
import {
  Card, Table, Button, Row, Col, Typography, Space, Tag, message, Tooltip,
} from 'antd';
import { ReloadOutlined, ApiOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { listProcessors, reloadProcessors } from '../api/processors';
import type { ProcessorInfo } from '../types/processor';

const { Title, Text } = Typography;

export default function ProcessorManager() {
  const [items, setItems] = useState<ProcessorInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [reloading, setReloading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listProcessors();
      setItems(res.data);
    } catch {
      message.error('获取处理器列表失败');
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
      const res = await reloadProcessors();
      message.success(`重载完成: ${res.data.total} 个处理器`);
      await fetchData();
    } catch {
      message.error('重载失败');
    } finally {
      setReloading(false);
    }
  };

  const columns: ColumnsType<ProcessorInfo> = [
    { title: '名称', dataIndex: 'name', key: 'name', width: 120,
      render: (v: string) => <Text code>{v}</Text>,
    },
    { title: '描述', dataIndex: 'description', key: 'description', width: 200 },
    { title: '实现类', dataIndex: 'class', key: 'class', width: 160,
      render: (v: string) => <Text type="secondary">{v}</Text>,
    },
    {
      title: '优先级', dataIndex: 'priority', key: 'priority', width: 80,
      render: (v: number) => <Tag>{v}</Tag>,
    },
    {
      title: '状态', key: 'status', width: 80,
      render: () => <Tag color="processing">活跃</Tag>,
    },
  ];

  return (
    <>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={4} style={{ margin: 0 }}>
            <ApiOutlined /> 处理器管理
          </Title>
          <Text type="secondary">{items.length} 个处理器</Text>
        </Col>
        <Col>
          <Button icon={<ReloadOutlined />} loading={reloading} onClick={handleReload}>
            热重载
          </Button>
        </Col>
      </Row>

      <Table
        columns={columns}
        dataSource={items}
        rowKey="name"
        loading={loading}
        scroll={{ x: 'max-content' }}
        pagination={false}
        size="small"
      />
    </>
  );
}
