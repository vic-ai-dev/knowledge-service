import { useState } from 'react';
import { Layout, Menu } from 'antd';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  DashboardOutlined,
  FileTextOutlined,
  RobotOutlined,
  DatabaseOutlined,
  CloudUploadOutlined,
  HistoryOutlined,
  SearchOutlined,
  BarChartOutlined,
} from '@ant-design/icons';

const { Sider, Content } = Layout;

const menuItems = [
  { key: '/overview', icon: <DashboardOutlined />, label: '系统总览' },
  { key: '/admin/documents', icon: <FileTextOutlined />, label: '文档中心' },
  { key: '/assistant', icon: <RobotOutlined />, label: 'AI 知识检索' },
  { key: '/documents', icon: <DatabaseOutlined />, label: '数据浏览器' },
  { key: '/ingestion', icon: <CloudUploadOutlined />, label: 'Ingestion 管理' },
  { key: '/ingestion/traces', icon: <HistoryOutlined />, label: 'Ingestion 追踪' },
  { key: '/query', icon: <SearchOutlined />, label: 'Query 追踪' },
  { key: '/evaluation', icon: <BarChartOutlined />, label: '评估面板' },
];

export default function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        style={{ borderRight: '1px solid #f0f0f0' }}
      >
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontWeight: 700,
            fontSize: collapsed ? 14 : 18,
            letterSpacing: '0.02em',
            borderBottom: '1px solid rgba(255,255,255,0.1)',
          }}
        >
          {collapsed ? 'KS' : 'Knowledge Service'}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          defaultOpenKeys={[]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Content style={{ margin: 24, minHeight: 280 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
