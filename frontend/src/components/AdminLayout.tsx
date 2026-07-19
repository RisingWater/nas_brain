import { useMemo, useState } from 'react';
import { Layout, Menu, Button, theme } from 'antd';
import {
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  UserOutlined,
  CloudServerOutlined,
  FileTextOutlined,
  ToolOutlined,
  SoundOutlined,
  ClockCircleOutlined,
  ThunderboltOutlined,
  ExperimentOutlined,
  MessageOutlined,
  DatabaseOutlined,
  CustomerServiceOutlined,
  UserSwitchOutlined,
  SettingOutlined,
  RobotOutlined,
  BellOutlined,
  AppstoreOutlined,
  FolderOutlined,
  BarChartOutlined,
  DownloadOutlined,
} from '@ant-design/icons';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';

const { Header, Sider, Content } = Layout;

const menuItems = [
  { key: '/', icon: <BarChartOutlined />, label: '监控面板' },
  {
    key: 'brain', icon: <RobotOutlined />, label: '智能引擎',
    children: [
      { key: '/users', icon: <UserOutlined />, label: '用户策略' },
      { key: '/chat-history', icon: <MessageOutlined />, label: '聊天记录' },
      { key: '/memory', icon: <DatabaseOutlined />, label: '记忆管理' },
      { key: '/traces', icon: <ClockCircleOutlined />, label: '请求追踪' },
    ],
  },
  {
    key: 'voice', icon: <SoundOutlined />, label: '语音网关',
    children: [
      { key: '/wakeword', icon: <CustomerServiceOutlined />, label: '唤醒词' },
      { key: '/voiceprints', icon: <UserSwitchOutlined />, label: '声纹管理' },
      { key: '/tts-cache', icon: <FolderOutlined />, label: 'TTS 缓存' },
    ],
  },
  {
    key: 'schedule', icon: <ClockCircleOutlined />, label: '定时任务',
    children: [
      { key: '/schedules', icon: <BellOutlined />, label: '定时提醒' },
      { key: '/detectors', icon: <ThunderboltOutlined />, label: '定时任务' },
    ],
  },
  {
    key: 'tools', icon: <ToolOutlined />, label: '工具插件',
    children: [
      { key: '/tools', icon: <AppstoreOutlined />, label: '工具管理' },
      { key: '/processors', icon: <ExperimentOutlined />, label: '处理器' },
    ],
  },
  {
    key: 'system', icon: <SettingOutlined />, label: '系统维护',
    children: [
      { key: '/services', icon: <CloudServerOutlined />, label: '服务管理' },
      { key: '/logs', icon: <FileTextOutlined />, label: '日志查看' },
      { key: '/backup', icon: <DownloadOutlined />, label: '数据备份' },
    ],
  },
];

export default function AdminLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);
  const {
    token: { colorBgContainer, borderRadiusLG },
  } = theme.useToken();

  // 根据当前路径找到对应的父菜单 key
  const openKeys = useMemo(() => {
    const path = location.pathname;
    for (const item of menuItems) {
      if (item.children?.some(c => c.key === path)) {
        return [item.key];
      }
    }
    return [];
  }, [location.pathname]);

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        breakpoint="lg"
        collapsedWidth={64}
        onBreakpoint={(broken) => setCollapsed(broken)}
        style={{ position: 'sticky', top: 0, height: '100vh' }}
      >
        <div
          style={{
            height: 32,
            margin: 16,
            color: '#fff',
            fontWeight: 'bold',
            fontSize: collapsed ? 14 : 16,
            textAlign: 'center',
            lineHeight: '32px',
            overflow: 'hidden',
            whiteSpace: 'nowrap',
          }}
        >
          {collapsed ? 'NB' : 'NAS Brain'}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          defaultOpenKeys={openKeys}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            padding: '0 16px',
            background: colorBgContainer,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
          />
          <span style={{ fontWeight: 500 }}>管理后台</span>
        </Header>
        <Content
          style={{
            margin: '12px',
            padding: 16,
            background: colorBgContainer,
            borderRadius: borderRadiusLG,
            minHeight: 280,
            overflow: 'auto',
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
