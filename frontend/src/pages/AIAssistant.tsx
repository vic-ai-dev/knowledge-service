import { useState, useRef } from 'react';
import {
  Card, Input, Button, List, Tag, Space, Segmented, Switch, Typography, Spin, Empty,
  Popconfirm, message, Divider, Tooltip, Flex
} from 'antd';
import {
  SendOutlined, RobotOutlined, UserOutlined, DeleteOutlined,
  SettingOutlined, LinkOutlined, HistoryOutlined,
  ReloadOutlined, PlusOutlined,
} from '@ant-design/icons';
import type { Conversation, Message, SearchMode } from '../types';

const { Text, Paragraph } = Typography;

const mockConversations: Conversation[] = Array.from({ length: 8 }, (_, i) => ({
  id: `conv-${String(i + 1).padStart(4, '0')}`,
  title: [
    '公司年假政策咨询',
    '技术架构讨论',
    '合规相关问答',
    '员工手册解读',
    '报销流程咨询',
    '绩效考核标准',
    'What is our deployment process?',
    'Onboarding checklist discussion',
  ][i],
  model: 'deepseek-v4-flash',
  collection: 'default',
  message_count: Math.floor(Math.random() * 12) + 1,
  created_at: new Date(Date.now() - i * 86400 * 1000 * 2).toISOString(),
  updated_at: new Date(Date.now() - i * 3600 * 1000).toISOString(),
}));

const mockMessages: Message[] = [
  {
    role: 'user',
    content: '公司的年假政策是什么？我入职满一年了，想知道可以休几天。',
    timestamp: new Date(Date.now() - 120000).toISOString(),
  },
  {
    role: 'assistant',
    content: '根据公司《员工手册》第四章第三节的规定：\n\n**年假政策概述**\n\n1. **入职满 1 年**：可享受 **10 个工作日** 年假\n2. **入职满 3 年**：可享受 **12 个工作日** 年假\n3. **入职满 5 年**：可享受 **15 个工作日** 年假\n\n> 备注：年假需在当年内休完，不可跨年累积。',
    timestamp: new Date(Date.now() - 90000).toISOString(),
    citations: [
      { document_id: 'doc-001', document_name: '员工手册_2024.pdf', chunk_id: 'chunk-001', score: 0.92, text: '第四章 员工福利...' },
      { document_id: 'doc-001', document_name: '员工手册_2024.pdf', chunk_id: 'chunk-002', score: 0.88, text: '年假管理细则...' },
    ],
  },
  {
    role: 'user',
    content: '那如果我有紧急情况需要请假，流程是怎样的？',
    timestamp: new Date(Date.now() - 60000).toISOString(),
  },
  {
    role: 'assistant',
    content: '紧急请假流程如下：\n\n1. **第一时间**通过企业微信联系直属上级\n2. 事后 **24 小时内**在 HR 系统补交请假申请\n3. 提供相关证明材料（病假需医院证明）\n\n> 若连续请假超过 3 天，需同时抄送部门负责人。',
    timestamp: new Date(Date.now() - 30000).toISOString(),
    citations: [
      { document_id: 'doc-002', document_name: '员工手册_考勤制度.pdf', chunk_id: 'chunk-015', score: 0.95, text: '紧急请假流程...' },
    ],
  },
];

export default function AIAssistant() {
  const [conversations] = useState<Conversation[]>(mockConversations);
  const [activeConv, setActiveConv] = useState<string>(conversations[0]?.id ?? '');
  const [messages, setMessages] = useState<Message[]>(mockMessages);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [searchMode, setSearchMode] = useState<SearchMode>('hybrid');
  const [rerankEnabled, setRerankEnabled] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const handleSend = async () => {
    if (!inputValue.trim()) return;
    const userMsg: Message = {
      role: 'user',
      content: inputValue.trim(),
      timestamp: new Date().toISOString(),
    };
    setMessages(prev => [...prev, userMsg]);
    setInputValue('');
    setLoading(true);
    // Simulate AI response
    const mockResp: Message = {
      role: 'assistant',
      content: '这是一个模拟回复。后端对接后将返回真实的检索增强生成结果。',
      timestamp: new Date().toISOString(),
      citations: [
        { document_id: 'doc-demo', document_name: '示例文档.pdf', chunk_id: 'chunk-demo', score: 0.85, text: '模拟引用内容...' },
      ],
    };
    setTimeout(() => {
      setMessages(prev => [...prev, mockResp]);
      setLoading(false);
    }, 1500);
  };

  const handleNewChat = () => {
    setMessages([]);
    setActiveConv('');
  };

  return (
    <Flex style={{ height: 'calc(100vh - 120px)', gap: 16 }}>
      {/* Conversation sidebar */}
      <Card
        title={
          <Space>
            <HistoryOutlined />
            <span>对话历史</span>
          </Space>
        }
        extra={
          <Tooltip title="新建对话">
            <Button type="text" icon={<PlusOutlined />} onClick={handleNewChat} />
          </Tooltip>
        }
        style={{ width: 280, flexShrink: 0 }}
        styles={{ body: { padding: 8, overflow: 'auto', flex: 1 } }}
      >
        {conversations.length === 0 ? (
          <Empty description="暂无对话" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        ) : (
          <List
            dataSource={conversations}
            renderItem={conv => (
              <List.Item
                onClick={() => setActiveConv(conv.id)}
                style={{
                  cursor: 'pointer',
                  padding: '8px 12px',
                  borderRadius: 6,
                  background: activeConv === conv.id ? '#f3e8ff' : 'transparent',
                  marginBottom: 2,
                }}
                actions={[
                  <Popconfirm
                    key="delete"
                    title="确认删除此对话？"
                    onConfirm={() => message.success('已删除')}
                  >
                    <Button type="text" size="small" danger icon={<DeleteOutlined />} />
                  </Popconfirm>,
                ]}
              >
                <List.Item.Meta
                  title={<Text style={{ fontSize: 13 }}>{conv.title}</Text>}
                  description={
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      {conv.message_count} 条消息 · {new Date(conv.updated_at).toLocaleDateString()}
                    </Text>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Card>

      {/* Chat area */}
      <Flex vertical style={{ flex: 1, minWidth: 0 }}>
        {/* Settings bar */}
        <Card
          size="small"
          style={{ marginBottom: 12 }}
          styles={{ body: { padding: '8px 16px' } }}
        >
          <Flex align="center" justify="space-between" wrap="wrap" gap={8}>
            <Space>
              <SettingOutlined />
              <Text strong>检索设置</Text>
              <Segmented<SearchMode>
                value={searchMode}
                onChange={setSearchMode}
                options={[
                  { value: 'vector', label: '仅向量检索' },
                  { value: 'hybrid', label: '混合检索' },
                ]}
              />
            </Space>
            <Space>
              <Text>重排序:</Text>
              <Switch checked={rerankEnabled} onChange={setRerankEnabled} />
            </Space>
          </Flex>
        </Card>

        {/* Messages area */}
        <Card
          style={{ flex: 1, overflow: 'auto', marginBottom: 12 }}
          styles={{ body: { padding: 16 } }}
        >
          {messages.length === 0 ? (
            <Empty description="开始新的对话吧！" style={{ marginTop: 80 }} />
          ) : (
            <Flex vertical gap={16}>
              {messages.map((msg, i) => (
                <Flex
                  key={i}
                  vertical
                  align={msg.role === 'user' ? 'flex-end' : 'flex-start'}
                >
                  <Flex gap={8} align="flex-start" style={{ maxWidth: '75%' }}>
                    {msg.role === 'assistant' && (
                      <RobotOutlined style={{ fontSize: 20, color: '#7C3AED', marginTop: 4 }} />
                    )}
                    <div
                      style={{
                        background: msg.role === 'user' ? '#7C3AED' : '#f5f5f5',
                        color: msg.role === 'user' ? '#fff' : '#333',
                        padding: '10px 14px',
                        borderRadius: 12,
                        borderBottomLeftRadius: msg.role === 'user' ? 12 : 4,
                        borderBottomRightRadius: msg.role === 'user' ? 4 : 12,
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                      }}
                    >
                      <Paragraph style={{ margin: 0, color: 'inherit', whiteSpace: 'pre-wrap' }}>
                        {msg.content}
                      </Paragraph>
                      {msg.citations && msg.citations.length > 0 && (
                        <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid rgba(0,0,0,0.08)' }}>
                          <Text style={{ fontSize: 12, color: msg.role === 'user' ? 'rgba(255,255,255,0.7)' : '#999' }}>
                            <LinkOutlined /> 引用来源:
                          </Text>
                          <Flex wrap="wrap" gap={4} style={{ marginTop: 4 }}>
                            {msg.citations.map((cit, j) => (
                              <Tag
                                key={j}
                                style={{ fontSize: 11, cursor: 'pointer', margin: 0 }}
                                color="purple"
                                bordered={false}
                              >
                                {cit.document_name} ({(cit.score * 100).toFixed(0)}%)
                              </Tag>
                            ))}
                          </Flex>
                        </div>
                      )}
                    </div>
                    {msg.role === 'user' && (
                      <UserOutlined style={{ fontSize: 20, color: '#7C3AED', marginTop: 4 }} />
                    )}
                  </Flex>
                </Flex>
              ))}
              {loading && (
                <Flex justify="flex-start">
                  <Space>
                    <Spin size="small" />
                    <Text type="secondary" style={{ fontSize: 13 }}>AI 正在思考...</Text>
                  </Space>
                </Flex>
              )}
              <div ref={messagesEndRef} />
            </Flex>
          )}
        </Card>

        {/* Input area */}
        <Flex gap={8}>
          <Input.TextArea
            value={inputValue}
            onChange={e => setInputValue(e.target.value)}
            placeholder="输入您的问题..."
            autoSize={{ minRows: 2, maxRows: 6 }}
            onPressEnter={e => {
              if (!e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
          />
          <Flex vertical gap={4} justify="end">
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={handleSend}
              loading={loading}
              style={{ height: 40 }}
            >
              发送
            </Button>
          </Flex>
        </Flex>
      </Flex>
    </Flex>
  );
}
