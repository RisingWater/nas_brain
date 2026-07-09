import { useEffect, useState, useCallback } from 'react';
import {
  Card, Table, Button, Row, Col, Typography, Space, message, Popconfirm, Tag,
  Modal, Form, Input, Select, Switch, DatePicker, TimePicker, Tooltip,
} from 'antd';
import {
  PlusOutlined, DeleteOutlined, PlayCircleOutlined, EditOutlined, ReloadOutlined,
} from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import { listSchedules, createSchedule, updateSchedule, deleteSchedule, triggerSchedule } from '../api/schedules';
import type { Schedule } from '../types/schedule';

const { Title, Text } = Typography;
const { Option } = Select;

const RTYPE_CN: Record<string, string> = { once: '一次性', daily: '每天', monthly: '每月' };
const STRATEGY_CN: Record<string, string> = { smart: 'Smart', direct: 'Direct' };
const NOTIFY_CN: Record<string, string> = { wechat: '微信', voice: '语音' };

export default function ScheduleManager() {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Schedule | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [form] = Form.useForm();

  const fetchData = useCallback(async (p?: number) => {
    setLoading(true);
    try {
      const res = await listSchedules({ page: p ?? page, page_size: 50 });
      setSchedules(res.data.schedules);
      setTotal(res.data.total);
    } catch {
      message.error('获取列表失败');
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    fetchData(1);
  }, [fetchData]);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ rtype: 'once', strategy: 'direct', notify_type: 'wechat', lunar: false });
    setModalOpen(true);
  };

  const openEdit = (s: Schedule) => {
    setEditing(s);
    const vals: Record<string, unknown> = {
      content: s.content,
      rtype: s.rtype,
      strategy: s.strategy,
      notify_type: s.notify_type,
      lunar: s.lunar,
      notify_target: s.notify_target || '',
    };
    if (s.rdatetime) {
      if (s.rtype === 'once') {
        vals.rdatetime = dayjs(s.rdatetime, 'YYYY-MM-DD HH:mm');
      } else if (s.rtype === 'daily') {
        vals.rdatetime = dayjs(s.rdatetime, 'HH:mm');
      } else if (s.rtype === 'monthly') {
        const [d, t] = s.rdatetime.split(' ');
        vals.rdatetime = dayjs(t, 'HH:mm');
        vals.month_day = parseInt(d);
      }
    }
    form.setFieldsValue(vals);
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);

      const data: Record<string, unknown> = {
        content: values.content,
        rtype: values.rtype,
        strategy: values.strategy,
        notify_type: values.notify_type,
        lunar: values.lunar || false,
        creator_id: values.creator_id || 'u_unknown',
        notify_target: values.notify_target || '',
      };

      if (values.rtype === 'once') {
        data.rdatetime = values.rdatetime.format('YYYY-MM-DD HH:mm');
      } else if (values.rtype === 'daily') {
        data.rdatetime = values.rdatetime.format('HH:mm');
      } else if (values.rtype === 'monthly') {
        data.rdatetime = `${values.month_day} ${values.rdatetime.format('HH:mm')}`;
      }

      if (editing) {
        await updateSchedule(editing.id, data);
        message.success('已更新');
      } else {
        await createSchedule(data);
        message.success('已创建');
      }

      setModalOpen(false);
      await fetchData(page);
    } catch {
      // form validation error or api error
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteSchedule(id);
      message.success('已删除');
      await fetchData(page);
    } catch {
      message.error('删除失败');
    }
  };

  const handleTrigger = async (id: number) => {
    try {
      await triggerSchedule(id);
      message.success('已触发');
    } catch {
      message.error('触发失败');
    }
  };

  const columns: ColumnsType<Schedule> = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    {
      title: '内容', dataIndex: 'content', key: 'content', width: 250,
      render: (v: string) => <Text ellipsis={{ tooltip: v }} style={{ maxWidth: 240 }}>{v}</Text>,
    },
    {
      title: '类型', dataIndex: 'rtype', key: 'rtype', width: 80,
      render: (v: string) => <Tag>{RTYPE_CN[v] || v}</Tag>,
    },
    {
      title: '时间', dataIndex: 'rdatetime', key: 'rdatetime', width: 150,
      render: (v: string | null) => v || '-',
    },
    {
      title: '策略', key: 'strategy', width: 80,
      render: (_, r) => (
        <Tag color={r.strategy === 'smart' ? 'blue' : 'green'}>{STRATEGY_CN[r.strategy]}</Tag>
      ),
    },
    {
      title: '通知', dataIndex: 'notify_type', key: 'notify_type', width: 60,
      render: (v: string) => <Text code>{NOTIFY_CN[v] || v}</Text>,
    },
    {
      title: '接收人', dataIndex: 'notify_target', key: 'notify_target', width: 120,
      render: (v: string | null) => v || <Text type="secondary">自己</Text>,
    },
    {
      title: '状态', dataIndex: 'done', key: 'done', width: 70,
      render: (v: boolean) => v
        ? <Tag color="default">已完成</Tag>
        : <Tag color="processing">待执行</Tag>,
    },
    {
      title: '操作', key: 'action', width: 140,
      render: (_, record) => (
        <Space>
          <Tooltip title="编辑">
            <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(record)} />
          </Tooltip>
          <Tooltip title="手动触发">
            <Button size="small" icon={<PlayCircleOutlined />} onClick={() => handleTrigger(record.id)} />
          </Tooltip>
          <Popconfirm title="删除此定时提醒？" onConfirm={() => handleDelete(record.id)} okText="删除" cancelText="取消">
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={4} style={{ margin: 0 }}>定时提醒管理</Title>
          <Text type="secondary">共 {total} 条</Text>
        </Col>
        <Col>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => fetchData(1)} loading={loading}>刷新</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新建</Button>
          </Space>
        </Col>
      </Row>

      <Table
        columns={columns}
        dataSource={schedules}
        rowKey="id"
        loading={loading}
        scroll={{ x: 'max-content' }}
        pagination={{
          current: page,
          total,
          pageSize: 50,
          onChange: (p) => { setPage(p); fetchData(p); },
          showTotal: (t) => `共 ${t} 条`,
        }}
        size="small"
      />

      <Modal
        title={editing ? '编辑定时提醒' : '新建定时提醒'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        confirmLoading={submitting}
        width={520}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="content" label="提醒内容" rules={[{ required: true, message: '请输入内容' }]}>
            <Input.TextArea rows={2} maxLength={2000} />
          </Form.Item>
          <Form.Item name="rtype" label="类型" rules={[{ required: true }]}>
            <Select>
              <Option value="once">一次性</Option>
              <Option value="daily">每天</Option>
              <Option value="monthly">每月</Option>
            </Select>
          </Form.Item>
          <Form.Item noStyle shouldUpdate={(prev, cur) => prev.rtype !== cur.rtype}>
            {({ getFieldValue }) => {
              const rtype = getFieldValue('rtype');
              if (rtype === 'once') {
                return (
                  <Form.Item name="rdatetime" label="执行时间" rules={[{ required: true }]}>
                    <DatePicker showTime format="YYYY-MM-DD HH:mm" style={{ width: '100%' }} />
                  </Form.Item>
                );
              }
              if (rtype === 'daily') {
                return (
                  <Form.Item name="rdatetime" label="执行时间" rules={[{ required: true }]}>
                    <TimePicker format="HH:mm" style={{ width: '100%' }} />
                  </Form.Item>
                );
              }
              if (rtype === 'monthly') {
                return (
                  <>
                    <Form.Item name="month_day" label="每月几号" rules={[{ required: true }]}>
                      <Input type="number" min={1} max={31} />
                    </Form.Item>
                    <Form.Item name="rdatetime" label="执行时间" rules={[{ required: true }]}>
                      <TimePicker format="HH:mm" style={{ width: '100%' }} />
                    </Form.Item>
                  </>
                );
              }
              return null;
            }}
          </Form.Item>
          <Form.Item name="lunar" label="农历" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="strategy" label="策略" rules={[{ required: true }]}>
            <Select>
              <Option value="direct">Direct（直接发送）</Option>
              <Option value="smart">Smart（LLM 处理）</Option>
            </Select>
          </Form.Item>
          <Form.Item name="notify_type" label="通知方式" rules={[{ required: true }]}>
            <Select>
              <Option value="wechat">微信</Option>
              <Option value="voice">语音</Option>
            </Select>
          </Form.Item>
          <Form.Item
            noStyle
            shouldUpdate={(prev, cur) => prev.notify_type !== cur.notify_type}
          >
            {({ getFieldValue }) =>
              getFieldValue('notify_type') === 'wechat' ? (
                <Form.Item
                  name="notify_target"
                  label="接收人（微信名/群名）"
                  help="留空则发给创建者自己"
                >
                  <Input placeholder="例如：学霸乔宝专项配套办公室" />
                </Form.Item>
              ) : null
            }
          </Form.Item>
          <Form.Item noStyle shouldUpdate={(prev, cur) => prev.strategy !== cur.strategy}>
            {({ getFieldValue }) => {
              if (getFieldValue('strategy') === 'smart') {
                return (
                  <Form.Item name="prompt" label="提示词（Smart 策略用）">
                    <Input.TextArea rows={2} placeholder="可选，留空则使用提醒内容" />
                  </Form.Item>
                );
              }
              return null;
            }}
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
