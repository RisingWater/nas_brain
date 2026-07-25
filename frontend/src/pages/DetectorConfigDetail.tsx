import { useEffect, useState } from 'react';
import {
  Typography, Button, Space, Spin, Card, Descriptions, Tag, Form, message, Divider,
} from 'antd';
import { ArrowLeftOutlined, PlayCircleOutlined, SaveOutlined } from '@ant-design/icons';
import { useParams, useNavigate } from 'react-router-dom';
import {
  listDetectors, getDetectorConfigSchema, getDetectorConfig,
  saveDetectorConfig, runDetector,
} from '../api/detectors';
import type { DetectorInfo } from '../types/detector';
import SchemaForm from '../components/SchemaForm';

const { Text } = Typography;

function formatInterval(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}min`;
  return `${Math.floor(seconds / 3600)}h`;
}

export default function DetectorConfigDetail() {
  const { name } = useParams<{ name: string }>();
  const navigate = useNavigate();

  const [detector, setDetector] = useState<DetectorInfo | null>(null);
  const [schema, setSchema] = useState<any>(null);
  const [configData, setConfigData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [form] = Form.useForm();

  useEffect(() => {
    if (!name) return;
    const load = async () => {
      setLoading(true);
      try {
        const [listRes, schemaRes, configRes] = await Promise.all([
          listDetectors(),
          getDetectorConfigSchema(name),
          getDetectorConfig(name),
        ]);
        const found = listRes.data.find((d: DetectorInfo) => d.name === name);
        setDetector(found || null);
        // Pydantic model_json_schema 可能会在 schema 层级包含 type/title
        // 需要确认 schema.data 就是 schema
        const s = schemaRes.data;
        setSchema(s);
        setConfigData(configRes.data);
        form.setFieldsValue(configRes.data);
      } catch {
        message.error('加载配置失败');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [name, form]);

  const handleSave = async () => {
    if (!name) return;
    try {
      const values = await form.validateFields();
      setSaving(true);
      await saveDetectorConfig(name, values);
      message.success('配置已保存');
      navigate('/detectors');
    } catch {
      message.error('保存配置失败');
    } finally {
      setSaving(false);
    }
  };

  const handleRun = async () => {
    if (!name) return;
    setRunning(true);
    try {
      await runDetector(name);
      message.success(`${name} 已运行`);
    } catch {
      message.error('运行失败');
    } finally {
      setRunning(false);
    }
  };

  if (loading) {
    return <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>;
  }

  if (!detector) {
    return <Text type="danger">未找到 Detector: {name}</Text>;
  }

  return (
    <div>
      {/* 顶部导航栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/detectors')}>
            返回列表
          </Button>
          <Text strong style={{ fontSize: 16 }}>{name}</Text>
        </Space>
        <Space>
          <Button icon={<PlayCircleOutlined />} loading={running} onClick={handleRun}>
            运行
          </Button>
          <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={handleSave}>
            保存
          </Button>
        </Space>
      </div>

      {/* Detector 信息卡片 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Descriptions column={4} size="small">
          <Descriptions.Item label="名称"><Text code>{detector.name}</Text></Descriptions.Item>
          <Descriptions.Item label="实现类">{detector.class}</Descriptions.Item>
          <Descriptions.Item label="运行间隔">
            <Tag>{formatInterval(detector.interval)}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="状态">
            {detector.enable
              ? <Tag color="processing">活跃</Tag>
              : <Tag color="default">已禁用</Tag>
            }
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* 配置表单 */}
      {schema ? (
        <Card size="small" title="配置">
          <SchemaForm schema={schema} form={form} />
        </Card>
      ) : (
        !loading && <Text type="secondary">该任务无可配置项</Text>
      )}
    </div>
  );
}
