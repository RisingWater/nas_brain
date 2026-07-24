import { useEffect, useState, useCallback } from 'react';
import {
  Card, Table, Button, Row, Col, Typography, Space, Tag, message, Switch,
  Drawer, Spin, Form,
} from 'antd';
import { ReloadOutlined, ApiOutlined, SettingOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { listDetectors, reloadDetectors, enableDetector, getDetectorConfigSchema, getDetectorConfig, saveDetectorConfig } from '../api/detectors';
import type { DetectorInfo } from '../types/detector';
import SchemaForm from '../components/SchemaForm';

const { Title, Text } = Typography;

export default function DetectorManager() {
  const [detectors, setDetectors] = useState<DetectorInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [reloading, setReloading] = useState(false);
  const [operating, setOperating] = useState<string | null>(null);

  // 配置 Drawer
  const [configOpen, setConfigOpen] = useState(false);
  const [configName, setConfigName] = useState('');
  const [configSchema, setConfigSchema] = useState<any>(null);
  const [configLoading, setConfigLoading] = useState(false);
  const [configSaving, setConfigSaving] = useState(false);
  const [configForm] = Form.useForm();

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

  const handleEnable = async (name: string, enable: boolean) => {
    setOperating(name);
    try {
      await enableDetector(name, enable);
      message.success(`${enable ? '启用' : '禁用'} ${name}`);
      await fetchData();
    } catch {
      message.error('操作失败');
    } finally {
      setOperating(null);
    }
  };

  // 配置
  const openConfig = async (name: string) => {
    setConfigName(name);
    setConfigOpen(true);
    setConfigLoading(true);
    setConfigSchema(null);
    configForm.resetFields();
    try {
      const [schemaRes, configRes] = await Promise.all([
        getDetectorConfigSchema(name),
        getDetectorConfig(name),
      ]);
      setConfigSchema(schemaRes.data);
      configForm.setFieldsValue(configRes.data);
    } catch {
      message.error('加载配置失败');
    } finally {
      setConfigLoading(false);
    }
  };

  const handleSaveConfig = async () => {
    try {
      const values = await configForm.validateFields();
      setConfigSaving(true);
      await saveDetectorConfig(configName, values);
      message.success('配置已保存');
      setConfigOpen(false);
      fetchData();  // 刷新列表（间隔等字段会更新）
    } catch {
      message.error('保存配置失败');
    } finally {
      setConfigSaving(false);
    }
  };

  const formatInterval = (seconds: number) => {
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}min`;
    return `${Math.floor(seconds / 3600)}h`;
  };

  const columns: ColumnsType<DetectorInfo> = [
    {
      title: '启用', key: 'enable', width: 60, align: 'center',
      render: (_, r) => (
        <Switch size="small" checked={r.enable} disabled={operating === r.name}
          onChange={(v) => handleEnable(r.name, v)} />
      ),
    },
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
      render: (_, r) => r.enable
        ? <Tag color="processing">活跃</Tag>
        : <Tag color="default">已禁用</Tag>,
    },
    {
      title: '配置', key: 'config', width: 70,
      render: (_, r) => (
        <Button type="link" size="small" icon={<SettingOutlined />}
                onClick={() => openConfig(r.name)}>
          配置
        </Button>
      ),
    },
  ];

  return (
    <>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
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

      <Drawer
        title={`${configName} 配置`}
        open={configOpen}
        onClose={() => setConfigOpen(false)}
        width={480}
        extra={
          <Button type="primary" loading={configSaving} onClick={handleSaveConfig}>
            保存
          </Button>
        }
        destroyOnClose
      >
        <Spin spinning={configLoading}>
          {configSchema ? (
            <SchemaForm schema={configSchema} form={configForm} />
          ) : (
            !configLoading && <Text type="secondary">该任务无可配置项</Text>
          )}
        </Spin>
      </Drawer>
    </>
  );
}
