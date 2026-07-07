import { useEffect } from 'react';
import { Form, Input, Select, Switch, Button, Space, message } from 'antd';
import type { User, CreateUserPayload, UpdateUserPayload } from '../types/user';
import { createUser, updateUser } from '../api/users';

interface Props {
  user: User | null;
  onSuccess: () => void;
  onCancel: () => void;
}

export default function UserForm({ user, onSuccess, onCancel }: Props) {
  const [form] = Form.useForm();
  const isEdit = !!user;

  useEffect(() => {
    if (user) {
      form.setFieldsValue({
        display_name: user.display_name,
        user_type: user.user_type,
        wechat_name: user.wechat_name || '',
        is_temp: user.is_temp,
      });
    } else {
      form.resetFields();
    }
  }, [user, form]);

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (isEdit) {
        const payload: UpdateUserPayload = { ...values };
        if (!payload.wechat_name) payload.wechat_name = null;
        await updateUser(user!.user_id, payload);
        message.success('更新成功');
      } else {
        const payload: CreateUserPayload = { ...values };
        if (!payload.wechat_name) payload.wechat_name = null;
        await createUser(payload);
        message.success('创建成功');
      }
      onSuccess();
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'errorFields' in err) {
        return; // 表单验证错误
      }
      message.error('操作失败');
    }
  };

  return (
    <Form
      form={form}
      layout="vertical"
      initialValues={{ user_type: 'person', is_temp: false, wechat_name: '' }}
    >
      <Form.Item
        name="display_name"
        label="姓名"
        rules={[{ required: true, message: '请输入姓名' }]}
      >
        <Input placeholder="请输入姓名" />
      </Form.Item>

      <Form.Item name="user_type" label="用户类型">
        <Select
          options={[
            { label: '个人', value: 'person' },
            { label: '群', value: 'group' },
          ]}
        />
      </Form.Item>

      <Form.Item name="wechat_name" label="微信名">
        <Input placeholder="选填" />
      </Form.Item>

      <Form.Item name="is_temp" label="临时用户" valuePropName="checked">
        <Switch />
      </Form.Item>

      <Form.Item>
        <Space>
          <Button type="primary" onClick={handleSubmit}>
            {isEdit ? '保存' : '创建'}
          </Button>
          <Button onClick={onCancel}>取消</Button>
        </Space>
      </Form.Item>
    </Form>
  );
}
