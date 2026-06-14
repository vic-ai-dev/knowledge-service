/* ============================================================================
 * Knowledge Service — AIAssistant AI 知识助手页面 (G10)
 * ============================================================================ */

import { useState, useRef, useCallback, useEffect } from 'react';
import {
  Card, Input, Button, List, Space, Segmented, Switch, Typography, Spin, Empty,
  Popconfirm, message, Flex, Tag,
} from 'antd';
import {
  SendOutlined, RobotOutlined, UserOutlined, DeleteOutlined,
  SettingOutlined, LinkOutlined, HistoryOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import type { Conversation, Message, SearchMode } from '../types';
import { askAssistant, getConversationHistory, deleteConversation, getConversationDetail } from '../api/assistant';

const { Text, Paragraph } = Typography;

export default function AIAssistant() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConv, setActiveConv] = useState<string>('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [convLoading, setConvLoading] = useState(true);
  const [searchMode, setSearchMode] = useState<SearchMode>('hybrid');
  const [rerankEnabled, setRerankEnabled] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [initialLoad, setInitialLoad] = useState(true);

  // 加载对话列表
  const fetchConversations = useCallback(async () => {
    setConvLoading(true);
    try {
      const result = await getConversationHistory({ page: 1, page_size: 50 });
      setConversations(result.items);
      if (result.items.length > 0 && !activeConv) {
        setActiveConv(result.items[0].id);
      }
    } catch (err: any) {
      console.error('Failed to load conversations:', err);
    } finally {
      setConvLoading(false);
      setInitialLoad(false);
    }
  }, []);

  // 加载指定对话的详情
  const fetchConversationDetail = useCallback(async (sessionId: string) => {
    try {
      const detail = await getConversationDetail(sessionId);
      if (detail && detail.messages) {
        setMessages(detail.messages);
      }
    } catch (err: any) {
      console.error('Failed to load conversation detail:', err);
      setMessages([]);
    }
  }, []);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  // 切换对话时加载详情
  useEffect(() => {
    if (activeConv) {
      fetchConversationDetail(activeConv);
    }
  }, [activeConv, fetchConversationDetail]);

  const handleSend = async () => {
    if (!inputValue.trim()) return;
    const userMsg: Message = {
      role: 'user',
      content: inputValue.trim(),
      timestamp: new Date().toISOString(),
    };
    setMessages(prev => [...prev, userMsg]);
    const queryText = inputValue.trim();
    setInputValue('');
    setLoading(true);

    try {
      const result = await askAssistant({
        query: queryText,
        search_mode: searchMode,
        rerank: rerankEnabled,
      });

      const assistantMsg: Message = {
        role: 'assistant',
        content: result.answer || '暂无回答',
        timestamp: new Date().toISOString(),
        citations: result.citations?.length > 0
          ? result.citations.map(c => ({
              chunk_id: c.chunk_id,
              text: c.text,
              source: typeof c.source === 'string' ? c.source : String(c.source || ''),
            }))
          : undefined,
      };
      setMessages(prev => [...prev, assistantMsg]);
    } catch (err: any) {
      message.error('请求失败: ' + (err.message || '未知错误'));
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: '抱歉，回答生成失败，请稍后重试。',
        timestamp: new Date().toISOString(),
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleNewChat = () => {
    setMessages([]);
    setActiveConv('');
  };

  const handleDeleteConv = async (convId: string) => {
    try {
      await deleteConversation(convId);
      message.success('对话已删除');
      setConversations(prev => prev.filter(c => c.id !== convId));
      if (activeConv === convId) {
        const remaining = conversations.filter(c => c.id !== convId);
        setActiveConv(remaining.length > 0 ? remaining[0].id : '');
        setMessages([]);
      }
    } catch (err: any) {
      message.error('删除失败: ' + (err.message || '未知错误'));
    }
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
          <Button type="text" icon={<PlusOutlined />} onClick={handleNewChat} />
        }
        style={{ width: 280, flexShrink: 0 }}
        styles={{ body: { padding: 8, overflow: 'auto', flex: 1 } }}
      >
        {initialLoad ? (
          <div style={{ textAlign: 'center', padding: 20 }}>
            <Spin size="small" />
          </div>
        ) : conversations.length === 0 ? (
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
                    onConfirm={() => handleDeleteConv(conv.id)}
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
          {messages.length === 0 && !loading ? (
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
                                {typeof cit.source === 'string' ? cit.source : '来源'}
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
