import { useEffect, useState, useCallback } from 'react';
import {
  Table, Button, Input, Select, Space, Tag, Popconfirm, message,
  Drawer, Card, Row, Col, Typography, Modal, Form, Radio, Switch,
  InputNumber, Transfer, Descriptions,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, SearchOutlined, ReloadOutlined, SettingOutlined } from '@ant-design/icons';
import type { ColumnsType, TransferItem } from 'antd/es/transfer';
import { listUsers, deleteUser } from '../api/users';
import type { User } from '../types/user';
import UserForm from './UserForm';
import {
  getUserConfig, updateUserConfig, listTools, listProcessors,
} from '../api/strategy';
import type { UserConfigUpdate } from '../api/strategy';

const { Title, Text } = Typography;
const DEFAULT_SYSTEM_PROMPT = '你是 NAS Brain，一个智能助手。请用中文回答用户的问题。';

const strategyColors: Record<string, string> = {
  smart: 'blue', direct: 'green', ignore: 'default',
};
const strategyLabels: Record<string, string> = {
  smart: 'Smart', direct: 'Direct', ignore: 'Ignore',
};

export default function UserList() {
  const [users, setUsers] = useState<User[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [keyword, setKeyword] = useState('');
  const [userType, setUserType] = useState<string | undefined>(undefined);
  const [formOpen, setFormOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);

  // 配置编辑
  const [configOpen, setConfigOpen] = useState(false);
  const [configUserId, setConfigUserId] = useState('');
  const [configSaving, setConfigSaving] = useState(false);
  const [configUserInfo, setConfigUserInfo] = useState<any>(null);
  const [allTools, setAllTools] = useState<TransferItem[]>([]);
  const [allProcessors, setAllProcessors] = useState<TransferItem[]>([]);
  const [userConfigs, setUserConfigs] = useState<Record<string, any>>({});
  const [configForm] = Form.useForm();

  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listUsers({ page, page_size: pageSize, keyword: keyword || undefined, user_type: userType });
      setUsers(res.data.users);
      setTotal(res.data.total);
      // 预加载所有用户配置
      const configPromises = res.data.users.map((u: User) =>
        getUserConfig(u.user_id).catch(() => null)
      );
      const configs = await Promise.all(configPromises);
      const configMap: Record<string, any> = {};
      res.data.users.forEach((u: User, i: number) => {
        if (configs[i]) configMap[u.user_id] = configs[i];
      });
      setUserConfigs(configMap);
    } catch {
      message.error('加载用户列表失败');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, keyword, userType]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  // 预加载工具和处理器列表
  useEffect(() => {
    Promise.all([
      listTools().then(tools => tools.map(t => ({ key: t.name, title: t.name, description: t.description }))).catch(() => []),
      listProcessors().then(ps => ps.map(p => ({ key: p.name, title: p.name, description: p.description }))).catch(() => []),
    ]).then(([tools, ps]) => {
      setAllTools(tools);
      setAllProcessors(ps);
    });
  }, []);

  const handleDelete = async (userId: string) => {
    try { await deleteUser(userId); message.success('删除成功'); fetchUsers(); }
    catch { message.error('删除失败'); }
  };

  const handleEdit = (user: User) => { setEditingUser(user); setFormOpen(true); };
  const handleCreate = () => { setEditingUser(null); setFormOpen(true); };
  const handleFormClose = () => { setFormOpen(false); setEditingUser(null); };
  const handleFormSuccess = () => { handleFormClose(); fetchUsers(); };

  const openConfigEditor = (user: User) => {
    setConfigUserId(user.user_id);
    setConfigUserInfo(user);
    setConfigOpen(true);
    // 加载配置并填充表单
    getUserConfig(user.user_id).then(config => {
      configForm.setFieldsValue({
        strategy: config.strategy,
        system_prompt: config.system_prompt || DEFAULT_SYSTEM_PROMPT,
        allowed_tools: config.allowed_tools || [],
        allowed_processors: config.allowed_processors || [],
        short_term_window: config.short_term_window,
        group_at_only: config.group_at_only,
      });
    }).catch(() => message.error('加载配置失败'));
  };

  const handleConfigSave = async () => {
    try {
      const values = await configForm.validateFields();
      setConfigSaving(true);
      const payload: UserConfigUpdate = {
        strategy: values.strategy,
        system_prompt: values.system_prompt === DEFAULT_SYSTEM_PROMPT ? '' : values.system_prompt,
        allowed_tools: values.strategy === 'smart' ? (values.allowed_tools?.length ? values.allowed_tools : null) : null,
        allowed_processors: values.strategy === 'direct' ? (values.allowed_processors?.length ? values.allowed_processors : null) : null,
        short_term_window: values.short_term_window,
        group_at_only: configUserInfo?.user_type === 'group' ? values.group_at_only : undefined,
      };
      await updateUserConfig(configUserId, payload);
      message.success('配置已保存');
      setConfigOpen(false);
      fetchUsers();
    } catch { message.error('保存失败'); }
    finally { setConfigSaving(false); }
  };

  const renderExpandedRow = (record: User) => {
    const cfg = userConfigs[record.user_id];
    if (!cfg) return <Text type="secondary">暂无配置</Text>;
    return (
      <div style={{ padding: '8px 0' }}>
        <Row gutter={[24, 8]}>
          <Col span={6}>
            <Text type="secondary">策略：</Text>
            <Tag color={strategyColors[cfg.strategy]}>{strategyLabels[cfg.strategy] || cfg.strategy}</Tag>
          </Col>
          <Col span={6}>
            <Text type="secondary">短期记忆：</Text>
            <Text>{cfg.short_term_window} 分钟</Text>
          </Col>
          {record.user_type === 'group' && (
            <Col span={6}>
              <Text type="secondary">@ 回复：</Text>
              <Text>{cfg.group_at_only ? '仅 @ 时回复' : '全部回复'}</Text>
            </Col>
          )}
        </Row>
        {cfg.system_prompt && (
          <Row style={{ marginTop: 4 }}>
            <Col span={24}>
              <Text type="secondary">System Prompt：</Text>
              <Text ellipsis style={{ maxWidth: 500 }}>{cfg.system_prompt}</Text>
            </Col>
          </Row>
        )}
        {cfg.strategy === 'smart' && cfg.allowed_tools && (
          <Row style={{ marginTop: 4 }}>
            <Col span={24}>
              <Text type="secondary">允许的工具：</Text>
              {cfg.allowed_tools.map((t: string) => <Tag key={t} style={{ marginTop: 2 }}>{t}</Tag>)}
            </Col>
          </Row>
        )}
        {cfg.strategy === 'direct' && cfg.allowed_processors && (
          <Row style={{ marginTop: 4 }}>
            <Col span={24}>
              <Text type="secondary">允许的处理器：</Text>
              {cfg.allowed_processors.map((p: string) => <Tag key={p} style={{ marginTop: 2 }}>{p}</Tag>)}
            </Col>
          </Row>
        )}
      </div>
    );
  };

  // 桌面端表格列
  const columns: ColumnsType<User> = [
    { title: 'ID', dataIndex: 'user_id', key: 'user_id', width: 120, responsive: ['lg' as const] },
    { title: '姓名', dataIndex: 'display_name', key: 'display_name', width: 120 },
    { title: '类型', dataIndex: 'user_type', key: 'user_type', width: 80,
      render: (t: string) => <Tag>{t === 'person' ? '个人' : t === 'group' ? '群' : t}</Tag>,
    },
    { title: '微信', dataIndex: 'wechat_name', key: 'wechat_name', width: 120, responsive: ['md' as const] },
    {
      title: '策略', key: 'strategy', width: 80,
      render: (_, record) => {
        const cfg = userConfigs[record.user_id];
        const s = cfg?.strategy || 'ignore';
        return <Tag color={strategyColors[s]}>{strategyLabels[s]}</Tag>;
      },
    },
    {
      title: '状态', dataIndex: 'is_active', key: 'is_active', width: 70,
      render: (v: boolean | null) =>
        v !== false ? <Tag color="green">正常</Tag> : <Tag color="red">停用</Tag>,
    },
    {
      title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 160,
      responsive: ['md' as const],
    },
    {
      title: '操作', key: 'action', width: 220, fixed: 'right' as const,
      render: (_, record) => (
        <Space>
          <Button type="link" size="small" icon={<SettingOutlined />} onClick={() => openConfigEditor(record)}>
            {isMobile ? '' : '配置'}
          </Button>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>
            {isMobile ? '' : '编辑'}
          </Button>
          <Popconfirm title="确定删除？" onConfirm={() => handleDelete(record.user_id)} okText="确定" cancelText="取消">
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              {isMobile ? '' : '删除'}
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <>
      {isMobile && (
        <Row gutter={[8, 8]} style={{ marginBottom: 12 }}>
          <Col span={24}>
            <Space.Compact style={{ width: '100%' }}>
              <Input placeholder="搜索姓名/微信" value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                onPressEnter={() => { setPage(1); fetchUsers(); }}
                prefix={<SearchOutlined />} allowClear />
              <Button icon={<ReloadOutlined />} onClick={() => { setPage(1); fetchUsers(); }} />
            </Space.Compact>
          </Col>
          <Col span={12}>
            <Select style={{ width: '100%' }} placeholder="全部类型" allowClear
              value={userType} onChange={(v) => { setUserType(v); setPage(1); }}
              options={[{ label: '全部', value: undefined }, { label: '个人', value: 'person' }, { label: '群', value: 'group' }]} />
          </Col>
          <Col span={12}>
            <Button type="primary" block icon={<PlusOutlined />} onClick={handleCreate}>新建</Button>
          </Col>
        </Row>
      )}

      {!isMobile && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col flex="auto">
            <Input.Search placeholder="搜索姓名 / 微信名" allowClear
              value={keyword} onChange={(e) => setKeyword(e.target.value)}
              onSearch={() => { setPage(1); fetchUsers(); }} enterButton />
          </Col>
          <Col>
            <Select style={{ width: 140 }} placeholder="用户类型" allowClear
              value={userType} onChange={(v) => { setUserType(v); setPage(1); }}
              options={[{ label: '全部类型', value: undefined }, { label: '个人', value: 'person' }, { label: '群', value: 'group' }]} />
          </Col>
          <Col>
            <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>新建用户</Button>
          </Col>
        </Row>
      )}

      {isMobile ? (
        <Row gutter={[8, 8]}>
          {users.map((u) => (
            <Col span={24} key={u.user_id}>
              <Card size="small" actions={[
                <EditOutlined key="edit" onClick={() => handleEdit(u)} />,
                <Popconfirm title="确定删除？" onConfirm={() => handleDelete(u.user_id)} key="delete">
                  <DeleteOutlined style={{ color: '#ff4d4f' }} />
                </Popconfirm>,
              ]}>
                <div style={{ fontWeight: 600 }}>{u.display_name}</div>
                <div style={{ color: '#888', fontSize: 12, marginTop: 4 }}>
                  {u.user_type} {u.wechat_name ? `| ${u.wechat_name}` : ''}
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      ) : (
        <Table
          columns={columns}
          dataSource={users}
          rowKey="user_id"
          loading={loading}
          scroll={{ x: 'max-content' }}
          expandable={{
            expandedRowRender: renderExpandedRow,
            rowExpandable: () => true,
          }}
          pagination={{
            current: page, pageSize, total,
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
            onChange: (p, ps) => { setPage(p); setPageSize(ps); },
          }}
        />
      )}

      {isMobile && (
        <Row justify="center" style={{ marginTop: 12 }}>
          <Col>
            <Space>
              <Button disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>上一页</Button>
              <span style={{ fontSize: 12 }}>{page} / {Math.ceil(total / pageSize)}</span>
              <Button disabled={page >= Math.ceil(total / pageSize)} onClick={() => setPage((p) => p + 1)}>下一页</Button>
            </Space>
          </Col>
        </Row>
      )}

      <Drawer title={editingUser ? '编辑用户' : '新建用户'} open={formOpen}
        onClose={handleFormClose} width={isMobile ? '100%' : 480} destroyOnClose>
        <UserForm user={editingUser} onSuccess={handleFormSuccess} onCancel={handleFormClose} />
      </Drawer>

      {/* 策略配置弹窗 */}
      <Modal title={configUserInfo ? `策略配置 — ${configUserInfo.display_name}` : '策略配置'}
        open={configOpen} onCancel={() => setConfigOpen(false)}
        onOk={handleConfigSave} confirmLoading={configSaving} width={640} destroyOnClose>
        {configUserInfo && (
          <Descriptions size="small" column={2} style={{ marginBottom: 16 }}>
            <Descriptions.Item label="ID">{configUserInfo.user_id}</Descriptions.Item>
            <Descriptions.Item label="类型">{configUserInfo.user_type === 'person' ? '个人' : '群'}</Descriptions.Item>
            <Descriptions.Item label="名称">{configUserInfo.display_name}</Descriptions.Item>
            <Descriptions.Item label="微信">{configUserInfo.wechat_name || '-'}</Descriptions.Item>
          </Descriptions>
        )}

        <Form form={configForm} layout="vertical"
          initialValues={{ strategy: 'ignore', allowed_tools: [], allowed_processors: [], short_term_window: 30, group_at_only: true }}>
          <Form.Item name="strategy" label="处理策略" rules={[{ required: true }]}>
            <Radio.Group>
              <Radio value="smart"><Text strong>Smart</Text><Text type="secondary"> — LLM + 工具调用，自动回复</Text></Radio><br />
              <Radio value="direct"><Text strong>Direct</Text><Text type="secondary"> — 处理器直出，指定处理器处理</Text></Radio><br />
              <Radio value="ignore"><Text strong>Ignore</Text><Text type="secondary"> — 只记录聊天记录，不处理</Text></Radio>
            </Radio.Group>
          </Form.Item>

          <Form.Item name="system_prompt" label="System Prompt（身份设定）">
            <Input.TextArea rows={3} placeholder={DEFAULT_SYSTEM_PROMPT} />
          </Form.Item>

          <Form.Item noStyle shouldUpdate={(prev, cur) => prev.strategy !== cur.strategy}>
            {({ getFieldValue }) => {
              if (getFieldValue('strategy') !== 'smart') return null;
              return (
                <Form.Item name="allowed_tools" label="允许的工具（左侧=已选，右侧=全部）"
                  valuePropName="targetKeys">
                  <Transfer dataSource={allTools}
                    render={(item) => `${item.title} — ${item.description}`}
                    titles={['已选', '全部']}
                    listStyle={{ width: 240, height: 260 }}
                    showSearch filterOption={(v, item) => (item.title as string || '').includes(v)} />
                </Form.Item>
              );
            }}
          </Form.Item>

          <Form.Item noStyle shouldUpdate={(prev, cur) => prev.strategy !== cur.strategy}>
            {({ getFieldValue }) => {
              if (getFieldValue('strategy') !== 'direct') return null;
              return (
                <Form.Item name="allowed_processors" label="允许的处理器（左侧=已选，右侧=全部）"
                  valuePropName="targetKeys">
                  <Transfer dataSource={allProcessors}
                    render={(item) => `${item.title} — ${item.description}`}
                    titles={['已选', '全部']}
                    listStyle={{ width: 240, height: 260 }}
                    showSearch filterOption={(v, item) => (item.title as string || '').includes(v)} />
                </Form.Item>
              );
            }}
          </Form.Item>

          {configUserInfo?.user_type === 'group' && (
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
