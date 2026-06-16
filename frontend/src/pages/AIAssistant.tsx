/* ============================================================================
 * Knowledge Service — RAG Query 页面 (G10)
 * 单次查询模式：搜索框 → 回答 + 引用 → 检索历史
 * ============================================================================ */

import { useState, useCallback, useEffect } from 'react';
import {
  Card, Input, Button, List, Space, Segmented, Switch, Typography, Spin, Empty,
  message, Flex, Tag, Pagination, Modal, Descriptions, Divider,
} from 'antd';
import {
  SearchOutlined, RobotOutlined, LinkOutlined, ClockCircleOutlined,
  FileTextOutlined, ThunderboltOutlined,
} from '@ant-design/icons';
import type { SearchMode, QueryResult, QueryTrace } from '../types';
import { askAssistant } from '../api/assistant';
import { getQueryTraces, getQueryTraceDetail } from '../api/query';

const { Text, Paragraph, Title } = Typography;

const PAGE_SIZE = 15;

function formatTime(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function AIAssistant() {
  // ── 查询状态 ──────────────────────────────────────────────
  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [queryResult, setQueryResult] = useState<QueryResult | null>(null);
  const [searchMode, setSearchMode] = useState<SearchMode>('hybrid');
  const [rerankEnabled, setRerankEnabled] = useState(true);
  const [hasSearched, setHasSearched] = useState(false);

  // ── 检索历史状态 ──────────────────────────────────────────
  const [traces, setTraces] = useState<QueryTrace[]>([]);
  const [tracesTotal, setTracesTotal] = useState(0);
  const [tracePage, setTracePage] = useState(1);
  const [tracesLoading, setTracesLoading] = useState(true);

  // ── 详情弹窗 ──────────────────────────────────────────────
  const [detailVisible, setDetailVisible] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailData, setDetailData] = useState<QueryTrace | null>(null);

  // ── 数据加载 ──────────────────────────────────────────────
  const fetchTraces = useCallback(async (page: number) => {
    setTracesLoading(true);
    try {
      const result = await getQueryTraces({ page, page_size: PAGE_SIZE });
      setTraces(result.items);
      setTracesTotal(result.total);
    } catch {
      setTraces([]);
      setTracesTotal(0);
    } finally {
      setTracesLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTraces(tracePage);
  }, [fetchTraces, tracePage]);

  // ── 查询 ──────────────────────────────────────────────────
  const handleSearch = async () => {
    const q = query.trim();
    if (!q) return;
    setSearching(true);
    setHasSearched(true);
    try {
      const result = await askAssistant({ query: q, search_mode: searchMode, rerank: rerankEnabled });
      setQueryResult(result);
      fetchTraces(1);
      setTracePage(1);
    } catch (err: any) {
      message.error('查询失败: ' + (err.message || '未知错误'));
      setQueryResult(null);
    } finally {
      setSearching(false);
    }
  };

  // ── 历史详情 ──────────────────────────────────────────────
  const handleViewDetail = async (traceId: string) => {
    setDetailVisible(true);
    setDetailLoading(true);
    try {
      const detail = await getQueryTraceDetail(traceId);
      setDetailData(detail);
    } catch {
      message.error('加载详情失败');
      setDetailData(null);
    } finally {
      setDetailLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      <Title level={3} style={{ marginBottom: 16 }}>AI 知识检索</Title>

      {/* ── Settings Bar ──────────────────────────────────── */}
      <Card size="small" style={{ marginBottom: 20 }} styles={{ body: { padding: '8px 16px' } }}>
        <Flex align="center" justify="space-between" wrap="wrap" gap={8}>
          <Space>
            <Text strong style={{ fontSize: 13 }}>检索模式</Text>
            <Segmented<SearchMode>
              value={searchMode}
              onChange={setSearchMode}
              options={[
                { value: 'vector_only', label: '仅向量检索' },
                { value: 'hybrid', label: '混合检索' },
              ]}
            />
          </Space>
          <Space>
            <Text style={{ fontSize: 13 }}>重排序</Text>
            <Switch checked={rerankEnabled} onChange={setRerankEnabled} size="small" />
          </Space>
        </Flex>
      </Card>

      {/* ── Search Bar ────────────────────────────────────── */}
      <div style={{ marginBottom: queryResult ? 24 : 48 }}>
        <Input.Search
          size="large"
          placeholder="输入您的问题，检索知识库..."
          enterButton="检索"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onSearch={handleSearch}
          loading={searching}
          style={{ maxWidth: 720, display: 'block', margin: '0 auto' }}
        />
      </div>

      {/* ── 搜索结果 ──────────────────────────────────────── */}
      {hasSearched && (
        <div style={{ marginBottom: 32 }}>
          {searching ? (
            <Flex justify="center" style={{ padding: 40 }}>
              <Spin tip="正在检索知识库…" />
            </Flex>
          ) : queryResult ? (
            <Card
              style={{ marginBottom: 16, borderLeft: '3px solid #7C3AED' }}
              styles={{ body: { padding: 16 } }}
            >
              <Flex gap={12} align="flex-start">
                <RobotOutlined style={{ fontSize: 24, color: '#7C3AED', marginTop: 2 }} />
                <div style={{ flex: 1 }}>
                  <Flex justify="space-between" align="center" style={{ marginBottom: 8 }}>
                    <Text strong>回答</Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      <ClockCircleOutlined /> {(queryResult.total_latency_ms || 0).toFixed(0)}ms
                    </Text>
                  </Flex>
                  <Paragraph style={{ margin: 0, whiteSpace: 'pre-wrap', color: '#333' }}>
                    {queryResult.answer || '暂无回答'}
                  </Paragraph>

                  {queryResult.citations && queryResult.citations.length > 0 && (
                    <div style={{ marginTop: 12, paddingTop: 10, borderTop: '1px solid #f0f0f0' }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        <LinkOutlined /> 引用来源:
                      </Text>
                      <div style={{ marginTop: 6 }}>
                        <Flex wrap="wrap" gap={4}>
                          {queryResult.citations.map((cit, i) => (
                            <Tag key={i} color="purple" bordered={false} style={{ fontSize: 11, margin: 0 }}>
                              {cit.source || `来源 ${i + 1}`}
                            </Tag>
                          ))}
                        </Flex>
                      </div>
                    </div>
                  )}

                  {queryResult.trace_id && (
                    <div style={{ marginTop: 8 }}>
                      <Text type="secondary" style={{ fontSize: 11 }}>
                        Trace: {queryResult.trace_id}
                      </Text>
                    </div>
                  )}
                </div>
              </Flex>
            </Card>
          ) : (
            <Empty description="未检索到结果" style={{ padding: 24 }} />
          )}
        </div>
      )}

      <Divider orientation="left" plain style={{ fontSize: 14, color: '#999' }}>
        检索历史
      </Divider>

      {/* ── 检索历史 ──────────────────────────────────────── */}
      <Card styles={{ body: { padding: 0 } }}>
        {tracesLoading ? (
          <Flex justify="center" style={{ padding: 40 }}>
            <Spin />
          </Flex>
        ) : traces.length === 0 ? (
          <Empty description="暂无检索历史" image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ padding: 40 }} />
        ) : (
          <List
            dataSource={traces}
            renderItem={(trace) => (
              <List.Item
                style={{ cursor: 'pointer', padding: '12px 16px' }}
                onClick={() => handleViewDetail(trace.trace_id)}
                extra={
                  <Space size="small" wrap>
                    {trace.rejected ? (
                      <Tag color="red" style={{ fontSize: 11, margin: 0 }}>已拒绝</Tag>
                    ) : (
                      <Tag color="green" style={{ fontSize: 11, margin: 0 }}>通过</Tag>
                    )}
                    <Text type="secondary" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>
                      {trace.total_latency_ms}ms
                    </Text>
                    <Text type="secondary" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>
                      {formatTime(trace.created_at)}
                    </Text>
                  </Space>
                }
              >
                <List.Item.Meta
                  avatar={<FileTextOutlined style={{ color: '#7C3AED', fontSize: 16 }} />}
                  title={
                    <Text style={{ fontSize: 14 }} ellipsis={{ tooltip: trace.user_query }}>
                      {trace.user_query}
                    </Text>
                  }
                  description={
                    <Space size="small" wrap>
                      {trace.category && <Tag style={{ fontSize: 10, margin: 0 }}>{trace.category}</Tag>}
                      {trace.language && <Tag style={{ fontSize: 10, margin: 0 }}>{trace.language}</Tag>}
                      {trace.cache_hit && (
                        <Tag icon={<ThunderboltOutlined />} color="blue" style={{ fontSize: 10, margin: 0 }}>
                          缓存
                        </Tag>
                      )}
                    </Space>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Card>

      {/* ── 分页 ──────────────────────────────────────────── */}
      {tracesTotal > PAGE_SIZE && (
        <Flex justify="center" style={{ marginTop: 16 }}>
          <Pagination
            current={tracePage}
            total={tracesTotal}
            pageSize={PAGE_SIZE}
            onChange={(p) => setTracePage(p)}
            showSizeChanger={false}
            size="small"
          />
        </Flex>
      )}

      {/* ── 详情 Modal ────────────────────────────────────── */}
      <Modal
        title="查询详情"
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={null}
        width={640}
      >
        {detailLoading ? (
          <Flex justify="center" style={{ padding: 40 }}><Spin /></Flex>
        ) : detailData ? (
          <div>
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="查询内容" span={2}>
                <Text copyable>{detailData.user_query}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="耗时">{detailData.total_latency_ms}ms</Descriptions.Item>
              <Descriptions.Item label="Token 消耗">
                {detailData.input_tokens} / {detailData.output_tokens} (共 {detailData.total_tokens})
              </Descriptions.Item>
              <Descriptions.Item label="缓存命中">
                <Tag color={detailData.cache_hit ? 'green' : 'default'}>{detailData.cache_hit ? '是' : '否'}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="合规检查">
                {detailData.rejected ? (
                  <Tag color="red">{detailData.rejection_reason || '已拒绝'}</Tag>
                ) : (
                  <Tag color="green">通过 ({detailData.compliance_score ?? '-'})</Tag>
                )}
              </Descriptions.Item>
              <Descriptions.Item label="Trace ID" span={2}>
                <Text copyable style={{ fontSize: 12 }}>{detailData.trace_id}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="时间" span={2}>
                {formatTime(detailData.created_at)}
              </Descriptions.Item>
            </Descriptions>

            {detailData.error && (
              <div style={{ marginTop: 12 }}>
                <Text type="danger">{detailData.error}</Text>
              </div>
            )}
          </div>
        ) : (
          <Empty description="无法加载详情" />
        )}
      </Modal>
    </div>
  );
}
