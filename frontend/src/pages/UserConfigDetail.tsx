import { useEffect, useState } from 'react';
import {
  Typography, Button, Space, Card, Descriptions, Tag, Form, message,
  Radio, Input, InputNumber, Switch, Transfer, Spin, Tabs,
} from 'antd';
import { ArrowLeftOutlined, SaveOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { useParams, useNavigate } from 'react-router-dom';
import type { TransferItem } from 'antd/es/transfer';
import {
  getUserConfig, updateUserConfig, listUsers, listTools, listProcessors,
  triggerIceBreaker,
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
  const [testing, setTesting] = useState(false);
  const [allTools, setAllTools] = useState<TransferItem[]>([]);
  const [allProcessors, setAllProcessors] = useState<TransferItem[]>([]);
  const [form] = Form.useForm();

  const hasWechat = !!(userInfo?.wechat_name);

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
          ocr_image: config.ocr_image ?? false,
          send_bqb: config.send_bqb ?? false,
          bqb_probability: config.bqb_probability ?? 50,
          ice_breaker_enabled: config.ice_breaker_enabled,
          ice_breaker_prompt: config.ice_breaker_prompt || '',
          ice_breaker_trigger_minutes: config.ice_breaker_trigger_minutes ?? 15,
          ice_breaker_cooldown_minutes: config.ice_breaker_cooldown_minutes ?? 60,
          ice_breaker_sleep_start: config.ice_breaker_sleep_start || '01:00',
          ice_breaker_sleep_end: config.ice_breaker_sleep_end || '08:00',
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
        ocr_image: values.ocr_image,
        send_bqb: values.send_bqb,
        bqb_probability: values.bqb_probability,
        ...(hasWechat ? {
          ice_breaker_enabled: values.ice_breaker_enabled,
          ice_breaker_prompt: values.ice_breaker_prompt || '',
          ice_breaker_trigger_minutes: values.ice_breaker_trigger_minutes,
          ice_breaker_cooldown_minutes: values.ice_breaker_cooldown_minutes,
          ice_breaker_sleep_start: values.ice_breaker_sleep_start,
          ice_breaker_sleep_end: values.ice_breaker_sleep_end,
        } : {}),
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

  const handleTestTrigger = async () => {
    if (!userId || !userInfo?.wechat_name) return;
    const prompt = form.getFieldValue('ice_breaker_prompt') || '';
    if (!prompt) {
      message.warning('请先填写主动发言提示词');
      return;
    }
    setTesting(true);
    try {
      await triggerIceBreaker(userId, userInfo.wechat_name, prompt);
      message.success('已触发主动发言，请查看微信');
    } catch {
      message.error('触发失败');
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>;
  }

  const basicTab = (
    <>
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

      <Form.Item name="ocr_image" label="图片自动 OCR 识别" valuePropName="checked"
                 tooltip="收到图片时自动识别其中的文字，结果补充到消息内容中">
        <Switch />
      </Form.Item>

      <Form.Item name="send_bqb" label="发送表情包" valuePropName="checked"
                 tooltip="回复时按概率附带一张相关表情包图片">
        <Switch />
      </Form.Item>
      <Form.Item noStyle shouldUpdate={(prev, cur) => prev.send_bqb !== cur.send_bqb}>
        {({ getFieldValue }) => {
          if (!getFieldValue('send_bqb')) return null;
          return (
            <Form.Item name="bqb_probability" label="表情包概率（%）"
                       tooltip="每次回复时附带表情包的概率百分比">
              <InputNumber min={1} max={100} style={{ width: 120 }} />
            </Form.Item>
          );
        }}
      </Form.Item>
    </>
  );

  const proactiveTab = hasWechat ? (
    <>
      <Form.Item name="ice_breaker_enabled" label="启用主动发言" valuePropName="checked">
        <Switch onChange={(checked) => {
          if (checked) {
            const cur = form.getFieldValue('ice_breaker_prompt');
            if (!cur) {
              form.setFieldsValue({
                ice_breaker_prompt: form.getFieldValue('system_prompt') || '',
              });
            }
          }
        }} />
      </Form.Item>

      <Form.Item noStyle shouldUpdate={true}>
        {({ getFieldValue }) => {
          if (!getFieldValue('ice_breaker_enabled')) return null;
          return (
            <>
              <Form.Item name="ice_breaker_prompt" label="主动发言触发语"
                         tooltip="作为用户消息发给 LLM，触发它主动说话。空则用默认（群聊/个人不同）">
                <Input.TextArea rows={3} placeholder="请输入提示词..." />
              </Form.Item>
              <Form.Item name="ice_breaker_trigger_minutes" label="沉默触发时间（分钟）"
                         tooltip="用户/群聊无人发言超过此时间后触发">
                <InputNumber min={1} max={1440} style={{ width: 200 }} />
              </Form.Item>
              <Form.Item name="ice_breaker_cooldown_minutes" label="冷却间隔（分钟）"
                         tooltip="两次主动发言之间的最短间隔">
                <InputNumber min={5} max={1440} style={{ width: 200 }} />
              </Form.Item>
              <Form.Item name="ice_breaker_sleep_start" label="免打扰开始时间" tooltip="HH:MM 格式">
                <Input placeholder="01:00" style={{ width: 120 }} />
              </Form.Item>
              <Form.Item name="ice_breaker_sleep_end" label="免打扰结束时间" tooltip="HH:MM 格式">
                <Input placeholder="08:00" style={{ width: 120 }} />
              </Form.Item>
              <Form.Item>
                <Button icon={<ThunderboltOutlined />} loading={testing} onClick={handleTestTrigger}>
                  立即发言（测试提示词）
                </Button>
                <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
                  点击后立即用当前提示词生成一条消息发送
                </Text>
              </Form.Item>
            </>
          );
        }}
      </Form.Item>
    </>
  ) : (
    <Text type="secondary">该用户未配置微信名称，无法使用主动发言功能。</Text>
  );

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

      <Card size="small">
        <Form form={form} layout="vertical"
              initialValues={{
                strategy: 'ignore',
                allowed_tools: [],
                allowed_processors: [],
                short_term_window: 30,
                group_at_only: true,
              }}>
          <Tabs items={[
            { key: 'basic', label: '基础配置', children: basicTab },
            { key: 'proactive', label: '主动发言', children: proactiveTab },
          ]} />
        </Form>
      </Card>
    </div>
  );
}
