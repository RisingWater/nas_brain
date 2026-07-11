import { useEffect, useState } from 'react';
import {
  Table, Button, Tag, Modal, Form, Radio, Input, InputNumber, Switch,
  Transfer, Space, message, Spin, Typography, Descriptions,
} from 'antd';
import type { ColumnsType, TransferItem } from 'antd/es/transfer';
import { SettingOutlined } from '@ant-design/icons';
import {
  listUserConfigs, getUserConfig, updateUserConfig,
  listUsers, listTools, listProcessors,
} from '../api/strategy';
import type { UserConfigUpdate, ToolInfo, ProcessorInfo } from '../api/strategy';

const { Title, Text } = Typography;

const DEFAULT_SYSTEM_PROMPT = '你是 NAS Brain，一个智能助手。请用中文回答用户的问题。';

export default function StrategyConfig() {
  const [configs, setConfigs] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editingUserId, setEditingUserId] = useState('');
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();

  // 编辑器内加载的数据
  const [userInfo, setUserInfo] = useState<any>(null);
  const [allTools, setAllTools] = useState<ToolInfo[]>([]);
  const [allProcessors, setAllProcessors] = useState<ProcessorInfo[]>([]);

  const fetchConfigs = async () => {
    setLoading(true);
    try {
      const [configItems, userItems] = await Promise.all([
        listUserConfigs(),
        listUsers(),
      ]);
      // 合并用户信息到配置列表
      const userMap = new Map(userItems.map((u: any) => [u.user_id, u]));
      const merged = configItems.map((c: any) => ({
        ...c,
        display_name: userMap.get(c.user_id)?.display_name || c.user_id,
        user_type: userMap.get(c.user_id)?.user_type || '?',
        wechat_name: userMap.get(c.user_id)?.wechat_name || null,
      }));
      setConfigs(merged);
    } catch {
      message.error('加载配置列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchConfigs();
  }, []);

  const handleEdit = async (userId: string) => {
    setEditingUserId(userId);
    setEditOpen(true);
    try {
      const [config, tools, processors, users] = await Promise.all([
        getUserConfig(userId),
        listTools(),
        listProcessors(),
        listUsers(),
      ]);
      const user = users.find((u: any) => u.user_id === userId);
      setUserInfo(user || null);
      setAllTools(tools);
      setAllProcessors(processors);

      form.setFieldsValue({
        strategy: config.strategy,
        system_prompt: config.system_prompt || DEFAULT_SYSTEM_PROMPT,
        allowed_tools: config.allowed_tools || [],
        allowed_processors: config.allowed_processors || [],
        short_term_window: config.short_term_window,
        group_at_only: config.group_at_only,
      });
    } catch {
      message.error('加载配置失败');
    }
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);

      const payload: UserConfigUpdate = {
        strategy: values.strategy,
        system_prompt: values.system_prompt === DEFAULT_SYSTEM_PROMPT ? '' : values.system_prompt,
        allowed_tools: values.strategy === 'smart' ? (values.allowed_tools?.length ? values.allowed_tools : null) : null,
        allowed_processors: values.strategy === 'direct' ? (values.allowed_processors?.length ? values.allowed_processors : null) : null,
        short_term_window: values.short_term_window,
        group_at_only: values.group_at_only,
      };
      // 非群用户不传 group_at_only
      if (userInfo?.user_type !== 'group') {
        delete payload.group_at_only;
      }

      await updateUserConfig(editingUserId, payload);
      message.success('配置已保存');
      setEditOpen(false);
      fetchConfigs();
    } catch {
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  const toolTransferData: TransferItem[] = allTools.map((t) => ({
    key: t.name,
    title: t.name,
    description: t.description,
  }));

  const processorTransferData: TransferItem[] = allProcessors.map((p) => ({
    key: p.name,
    title: p.name,
    description: p.description,
  }));

  const strategyColors: Record<string, string> = {
    smart: 'blue',
    direct: 'green',
    ignore: 'default',
  };
  const strategyLabels: Record<string, string> = {
    smart: 'Smart',
    direct: 'Direct',
    ignore: 'Ignore',
  };

  const columns: ColumnsType<any> = [
    { title: '用户', dataIndex: 'display_name', key: 'display_name', width: 120 },
    { title: 'ID', dataIndex: 'user_id', key: 'user_id', width: 120, responsive: ['lg' as const] },
    {
      title: '类型', dataIndex: 'user_type', key: 'user_type', width: 70,
      render: (t: string) => <Tag>{t === 'person' ? '个人' : t === 'group' ? '群' : t}</Tag>,
    },
    {
      title: '策略', dataIndex: 'strategy', key: 'strategy', width: 90,
      render: (s: string) => <Tag color={strategyColors[s] || 'default'}>{strategyLabels[s] || s}</Tag>,
    },
    {
      title: '短期记忆', dataIndex: 'short_term_window', key: 'short_term_window', width: 90,
      render: (v: number) => `${v} 分钟`,
    },
    {
      title: '@ 回复', dataIndex: 'group_at_only', key: 'group_at_only', width: 70,
      render: (v: boolean) => v ? <Tag color="green">是</Tag> : <Tag>否</Tag>,
    },
    {
      title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', width: 150,
      responsive: ['lg' as const],
    },
    {
      title: '操作', key: 'action', width: 80,
      render: (_, record) => (
        <Button type="link" size="small" icon={<SettingOutlined />}
                onClick={() => handleEdit(record.user_id)}>
          编辑
        </Button>
      ),
    },
  ];

  return (
    <>
      <Title level={4} style={{ marginBottom: 16 }}>策略配置</Title>
      <Table
        columns={columns}
        dataSource={configs}
        rowKey="user_id"
        loading={loading}
        scroll={{ x: 'max-content' }}
        pagination={{ pageSize: 50, showTotal: (t) => `共 ${t} 条` }}
      />

      <Modal
        title={userInfo ? `策略配置 — ${userInfo.display_name}` : '策略配置'}
        open={editOpen}
        onCancel={() => setEditOpen(false)}
        onOk={handleSave}
        confirmLoading={saving}
        width={640}
        destroyOnClose
      >
        {userInfo && (
          <Descriptions size="small" column={2} style={{ marginBottom: 16 }}>
            <Descriptions.Item label="用户 ID">{userInfo.user_id}</Descriptions.Item>
            <Descriptions.Item label="类型">
              {userInfo.user_type === 'person' ? '个人' : userInfo.user_type === 'group' ? '群' : userInfo.user_type}
            </Descriptions.Item>
            <Descriptions.Item label="名称">{userInfo.display_name}</Descriptions.Item>
            <Descriptions.Item label="微信">{userInfo.wechat_name || '-'}</Descriptions.Item>
          </Descriptions>
        )}

        <Form form={form} layout="vertical"
              initialValues={{
                strategy: 'ignore',
                allowed_tools: [],
                allowed_processors: [],
                short_term_window: 30,
                group_at_only: true,
              }}>

          <Form.Item name="strategy" label="处理策略" rules={[{ required: true }]}>
            <Radio.Group>
              <Radio value="smart">
                <Text strong>Smart</Text>
                <Text type="secondary"> — LLM + 工具调用，自动回复</Text>
              </Radio>
              <br />
              <Radio value="direct">
                <Text strong>Direct</Text>
                <Text type="secondary"> — 处理器直出，指定处理器处理</Text>
              </Radio>
              <br />
              <Radio value="ignore">
                <Text strong>Ignore</Text>
                <Text type="secondary"> — 只记录聊天记录，不处理</Text>
              </Radio>
            </Radio.Group>
          </Form.Item>

          {/* 共同的 system prompt */}
          <Form.Item name="system_prompt" label="System Prompt（身份设定）">
            <Input.TextArea rows={3} />
          </Form.Item>

          {/* Smart 模式：工具选择 */}
          <Form.Item noStyle shouldUpdate={(prev, cur) => prev.strategy !== cur.strategy}>
            {({ getFieldValue }) => {
              const strategy = getFieldValue('strategy');
              if (strategy !== 'smart') return null;
              return (
                <Form.Item name="allowed_tools" label="允许的工具（左侧=已选，右侧=可选）"
                           valuePropName="targetKeys">
                  <Transfer
                    dataSource={toolTransferData}
                    render={(item) => `${item.title} — ${item.description}`}
                    titles={['已选工具', '全部工具']}
                    listStyle={{ width: 240, height: 280 }}
                    showSearch
                    filterOption={(v, item) => (item.title as string || '').includes(v)}
                  />
                </Form.Item>
              );
            }}
          </Form.Item>

          {/* Direct 模式：处理器选择 */}
          <Form.Item noStyle shouldUpdate={(prev, cur) => prev.strategy !== cur.strategy}>
            {({ getFieldValue }) => {
              const strategy = getFieldValue('strategy');
              if (strategy !== 'direct') return null;
              return (
                <Form.Item name="allowed_processors" label="允许的处理器（左侧=已选，右侧=可选）"
                           valuePropName="targetKeys">
                  <Transfer
                    dataSource={processorTransferData}
                    render={(item) => `${item.title} — ${item.description}`}
                    titles={['已选处理器', '全部处理器']}
                    listStyle={{ width: 240, height: 280 }}
                    showSearch
                    filterOption={(v, item) => (item.title as string || '').includes(v)}
                  />
                </Form.Item>
              );
            }}
          </Form.Item>

          {/* 群用户：@ 配置 */}
          {userInfo?.user_type === 'group' && (
            <Form.Item name="group_at_only" label="群聊仅 @ 时回复" valuePropName="checked">
              <Switch />
            </Form.Item>
          )}

          <Form.Item name="short_term_window" label="短期记忆窗口（分钟）" rules={[{ required: true }]}>
            <InputNumber min={5} max={1440} style={{ width: 200 }} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
