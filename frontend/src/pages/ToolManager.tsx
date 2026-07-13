import { useEffect, useState, useCallback } from 'react';
import {
  Card, Table, Button, Tag, Row, Col, Typography, Space, message, Tooltip,
} from 'antd';
import { ReloadOutlined, CodeOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { listTools, reloadTools } from '../api/tools';
import type { ToolInfo } from '../types/tool';

const { Title, Text, Paragraph } = Typography;

export default function ToolManager() {
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [reloading, setReloading] = useState(false);

  const fetchTools = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listTools();
      setTools(res.data);
    } catch {
      message.error('获取工具列表失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTools();
  }, [fetchTools]);

  const handleReload = async () => {
    setReloading(true);
    try {
      const res = await reloadTools();
      message.success(`重载完成: ${res.data.total} 个工具`);
      await fetchTools();
    } catch {
      message.error('重载失败');
    } finally {
      setReloading(false);
    }
  };

  const columns: ColumnsType<ToolInfo> = [
    { title: '工具名', dataIndex: 'name', key: 'name', width: 140,
      render: (name: string) => <Text code>{name}</Text>,
    },
    { title: '描述', dataIndex: 'description', key: 'description', width: 300 },
    {
      title: '参数', key: 'params', width: 200, responsive: ['lg' as const],
      render: (_, record) => {
        const props = record.parameters?.properties || {};
        const names = Object.keys(props);
        return names.length > 0
          ? <Text style={{ fontSize: 12 }}>{names.join(', ')}</Text>
          : <Text type="secondary">无</Text>;
      },
    },
    {
      title: '标记', key: 'flags', width: 120,
      render: (_, record) => (
        <Space>
          {record.silent && <Tag color="blue">silent</Tag>}
          {record.final && <Tag color="orange">final</Tag>}
        </Space>
      ),
    },
    {
      title: '操作', key: 'action', width: 80,
      render: (_, record) => (
        <Tooltip title="查看完整 schema">
          <Button size="small" icon={<CodeOutlined />}
            onClick={() => {
              navigator.clipboard.writeText(JSON.stringify(record.parameters, null, 2));
              message.info('Schema 已复制到剪贴板');
            }}
          />
        </Tooltip>
      ),
    },
  ];

  return (
    <>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Text type="secondary" style={{ fontSize: 12 }}>已加载 {tools.length} 个工具</Text>
        </Col>
        <Col>
          <Button icon={<ReloadOutlined />} loading={reloading} onClick={handleReload}>
            重载工具
          </Button>
        </Col>
      </Row>

      <Table
        columns={columns}
        dataSource={tools}
        rowKey="name"
        loading={loading}
        scroll={{ x: 'max-content' }}
        pagination={false}
        expandable={{
          expandedRowRender: (record) => (
            <pre style={{ fontSize: 12, maxHeight: 300, overflow: 'auto' }}>
              {JSON.stringify(record.parameters, null, 2)}
            </pre>
          ),
          rowExpandable: () => true,
        }}
      />
    </>
  );
}
