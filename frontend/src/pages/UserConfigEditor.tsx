import { useEffect, useState } from 'react';
import { Drawer, Form, Radio, Input, Select, InputNumber, Switch, Button, Space, message, Spin } from 'antd';
import { getUserConfig, updateUserConfig, listTools } from '../api/userConfig';
import type { UserConfigUpdate } from '../types/userConfig';
import type { ToolInfo } from '../api/userConfig';

interface Props {
  userId: string;
  displayName: string;
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export default function UserConfigEditor({ userId, displayName, open, onClose, onSuccess }: Props) {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [allTools, setAllTools] = useState<ToolInfo[]>([]);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    Promise.all([
      getUserConfig(userId),
      listTools(),
    ])
      .then(([config, toolsList]) => {
        form.setFieldsValue({
          strategy: config.strategy,
          system_prompt: config.system_prompt || '',
          allowed_tools: config.allowed_tools,
          short_term_window: config.short_term_window,
          group_at_only: config.group_at_only,
        });
        setAllTools(toolsList || []);
      })
      .catch(() => message.error('加载配置失败'))
      .finally(() => setLoading(false));
  }, [userId, open, form]);

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);

      // allowed_tools: ['__all__'] → null (全部工具)
      let allowedTools = values.allowed_tools;
      if (allowedTools && allowedTools.includes('__all__')) {
        allowedTools = null;
      }

      const payload: UserConfigUpdate = {
        strategy: values.strategy,
        system_prompt: values.system_prompt || '',
        allowed_tools: allowedTools,
        short_term_window: values.short_term_window,
        group_at_only: values.group_at_only,
      };

      await updateUserConfig(userId, payload);
      message.success('配置已保存');
      onSuccess();
      onClose();
    } catch {
      message.error('保存失败');
    } finally {
      setSaving(false);
    }
  };

  const toolOptions = [
    { label: '全部工具', value: '__all__' },
    ...allTools.map((t: ToolInfo) => ({
      label: `${t.name} — ${t.description}`,
      value: t.name,
    })),
  ];

  return (
    <Drawer
      title={`策略配置 — ${displayName} (${userId})`}
      open={open}
      onClose={onClose}
      width={520}
      destroyOnClose
      footer={
        <Space style={{ float: 'right' }}>
          <Button onClick={onClose}>取消</Button>
          <Button type="primary" loading={saving} onClick={handleSave}>保存</Button>
        </Space>
      }
    >
      {loading ? (
        <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
      ) : (
        <Form form={form} layout="vertical" initialValues={{ strategy: 'smart', short_term_window: 30, group_at_only: true }}>
          <Form.Item name="strategy" label="处理策略" rules={[{ required: true }]}>
            <Radio.Group>
              <Radio value="smart">Smart（LLM + 工具调用）</Radio>
              <Radio value="direct">Direct（处理器直出）</Radio>
            </Radio.Group>
          </Form.Item>

          <Form.Item name="system_prompt" label="System Prompt（身份设定）">
            <Input.TextArea rows={4} placeholder="留空使用默认 prompt" />
          </Form.Item>

          <Form.Item name="allowed_tools" label="允许的工具">
            <Select
              mode="multiple"
              placeholder="选择允许的工具（默认全部）"
              options={toolOptions}
              allowClear
              maxTagCount={5}
            />
          </Form.Item>

          <Form.Item name="short_term_window" label="短期记忆窗口（分钟）" rules={[{ required: true }]}>
            <InputNumber min={5} max={1440} style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item name="group_at_only" label="群聊仅 @ 时回复" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      )}
    </Drawer>
  );
}
