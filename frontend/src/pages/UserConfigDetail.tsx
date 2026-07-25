import { useEffect, useState } from 'react';
import {
  Typography, Button, Space, Card, Descriptions, Tag, Form, message,
  Radio, Input, InputNumber, Switch, Transfer, Spin,
} from 'antd';
import { ArrowLeftOutlined, SaveOutlined } from '@ant-design/icons';
import { useParams, useNavigate } from 'react-router-dom';
import type { TransferItem } from 'antd/es/transfer';
import {
  getUserConfig, updateUserConfig, listUsers, listTools, listProcessors,
} from '../api/strategy';
import type { UserConfigUpdate, ToolInfo, ProcessorInfo } from '../api/strategy';

const { Text } = Typography;
const DEFAULT_SYSTEM_PROMPT = '你是 NAS Brain，一个智能助手。请用中文回答用户的问题。';

export default function UserConfigDetail() {
  const { userId } = useParams<{ userId: string }>();
  const navigate = useNavigate();

  const [userInfo, setUserInfo] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [allTools, setAllTools] = useState<TransferItem[]>([]);
  const [allProcessors, setAllProcessors] = useState<TransferItem[]>([]);
  const [form] = Form.useForm();

  useEffect(() => {
    if (!userId) return;
    const load = async () => {
      setLoading(true);
      try {
        const [config, tools, processors, users] = await Promise.all([
          getUserConfig(userId),
          listTools(),
          listProcessors(),
          listUsers(),
        ]);

        const user = users.find((u: any) => u.user_id === userId);
        setUserInfo(user || null);
        setAllTools(
          tools.map((t: ToolInfo) => ({ key: t.name, title: t.name, description: t.description })),
        );
        setAllProcessors(
          processors.map((p: ProcessorInfo) => ({ key: p.name, title: p.name, description: p.description })),
        );

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
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [userId, form]);

  const handleSave = async () => {
    if (!userId) return;
    try {
      const values = await form.validateFields();
      setSaving(true);
      const payload: UserConfigUpdate = {
        strategy: values.strategy,
        system_prompt: values.system_prompt === DEFAULT_SYSTEM_PROMPT ? '' : values.system_prompt,
        allowed_tools: values.strategy === 'smart' ? (values.allowed_tools?.length ? values.allowed_tools : null) : null,
        allowed_processors: values.strategy === 'direct' ? (values.allowed_processors?.length ? values.allowed_processors : null) : null,
        short_term_window: values.short_term_window,
        group_at_only: userInfo?.user_type === 'group' ? values.group_at_only : undefined,
      };
      await updateUserConfig(userId, payload);
      message.success('配置已保存');
      navigate('/users');
    } catch {
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>;
  }

  return (
    <div>
      {/* 顶部导航栏 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/users')}>
            返回用户列表
          </Button>
          <Text strong style={{ fontSize: 16 }}>
            策略配置 — {userInfo?.display_name || userId}
          </Text>
        </Space>
        <Space>
          <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={handleSave}>
            保存
          </Button>
        </Space>
      </div>

      {/* 用户信息卡片 */}
      {userInfo && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <Descriptions column={4} size="small">
            <Descriptions.Item label="用户 ID"><Text code>{userInfo.user_id}</Text></Descriptions.Item>
            <Descriptions.Item label="类型">
              {userInfo.user_type === 'person' ? <Tag>个人</Tag> :
               userInfo.user_type === 'group' ? <Tag>群</Tag> :
               <Tag>{userInfo.user_type}</Tag>}
            </Descriptions.Item>
            <Descriptions.Item label="名称">{userInfo.display_name}</Descriptions.Item>
            <Descriptions.Item label="微信">{userInfo.wechat_name || '-'}</Descriptions.Item>
          </Descriptions>
        </Card>
      )}

      {/* 策略表单 */}
      <Card size="small" title="配置">
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

          <Form.Item name="system_prompt" label="System Prompt（身份设定）">
            <Input.TextArea rows={3} placeholder={DEFAULT_SYSTEM_PROMPT} />
          </Form.Item>

          {/* Smart 模式：工具选择 */}
          <Form.Item noStyle shouldUpdate={(prev, cur) => prev.strategy !== cur.strategy}>
            {({ getFieldValue }) => {
              if (getFieldValue('strategy') !== 'smart') return null;
              return (
                <Form.Item name="allowed_tools" label="允许的工具（左侧=已选，右侧=全部）"
                           valuePropName="targetKeys">
                  <Transfer
                    dataSource={allTools}
                    render={(item) => `${item.title} — ${item.description}`}
                    titles={['已选', '全部']}
                    listStyle={{ width: 240, height: 260 }}
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
              if (getFieldValue('strategy') !== 'direct') return null;
              return (
                <Form.Item name="allowed_processors" label="允许的处理器（左侧=已选，右侧=全部）"
                           valuePropName="targetKeys">
                  <Transfer
                    dataSource={allProcessors}
                    render={(item) => `${item.title} — ${item.description}`}
                    titles={['已选', '全部']}
                    listStyle={{ width: 240, height: 260 }}
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
      </Card>
    </div>
  );
}
