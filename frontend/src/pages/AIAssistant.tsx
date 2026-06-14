import { Card, Input, Button, List, Tag, Space, Segmented } from 'antd';
import { SendOutlined, RobotOutlined } from '@ant-design/icons';
import { useState } from 'react';

export default function AIAssistant() {
  const [query, setQuery] = useState('');

  return (
    <div style={{ display: 'flex', gap: 24, height: 'calc(100vh - 128px)' }}>
      <Card title="对话历史" style={{ width: 280, flexShrink: 0 }}>
        <p style={{ color: '#999' }}>暂无对话记录</p>
      </Card>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <Card
          title={
            <Space>
              <RobotOutlined />
              <span>AI 知识助手</span>
            </Space>
          }
          extra={
            <Space>
              <Segmented options={['hybrid', 'vector_only']} defaultValue="hybrid" />
              <Tag color="blue" style={{ cursor: 'pointer' }}>重排序: 开</Tag>
            </Space>
          }
          style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
          styles={{ body: { flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column' } }}
        >
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#999' }}>
            输入问题开始对话
          </div>
        </Card>

        <Input.Search
          size="large"
          placeholder="输入您的问题..."
          enterButton={<Button type="primary" icon={<SendOutlined />}>发送</Button>}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ marginTop: 16 }}
        />
      </div>
    </div>
  );
}
