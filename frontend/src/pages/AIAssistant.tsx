/* ============================================================================
 * Knowledge Service — AI 知识检索 (G10+G11)
 * 搜索框 → 回答 + 引用 + 查询历史 table (含 chunk popup)
 * ============================================================================ */

import { useState, useCallback, useEffect } from 'react';
import {
  Card, Input, Segmented, Switch, Typography, Spin, Empty,
  message, Flex, Tag, Button, Table, Modal, Descriptions, Divider, Row, Col, Statistic,
} from 'antd';
import {
  RobotOutlined, LinkOutlined, ClockCircleOutlined,
  ReloadOutlined, CloseCircleOutlined, WarningOutlined, CheckCircleOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import type { SearchMode, QueryResult, QueryTrace } from '../types';
import { executeQuery, getQueryTraces } from '../api/query';
import type { ColumnsType } from 'antd/es/table';

const { Text, Paragraph, Title } = Typography;
const PAGE_SIZE = 10;

const fmtMs = (ms: number | null | undefined) => {
  if (ms == null) return '—';
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${ms.toFixed(0)}ms`;
};

const fmtTime = (iso: string | null | undefined) => {
  if (!iso) return '-';
  return new Date(iso).toISOString().replace('T', ' ').slice(0, 19);
};

export default function AIAssistant() {
  // ── 查询状态 ──
  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [queryResult, setQueryResult] = useState<QueryResult | null>(null);
  const [searchMode, setSearchMode] = useState<SearchMode>('hybrid');
  const [rerankEnabled, setRerankEnabled] = useState(true);
  const [hasSearched, setHasSearched] = useState(false);

  // ── 检索历史 ──
  const [traces, setTraces] = useState<QueryTrace[]>([]);
  const [total, setTotal] = useState(0);
  const [tracePage, setTracePage] = useState(1);
  const [tracesLoading, setTracesLoading] = useState(true);

  // ── 详情弹窗 ──
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [selectedTrace, setSelectedTrace] = useState<QueryTrace | null>(null);

  // ── 加载检索历史 ──
  const fetchTraces = useCallback(async (page: number) => {
    setTracesLoading(true);
    try {
      const result = await getQueryTraces({ page, page_size: PAGE_SIZE });
      setTraces(result.items);
      setTotal(result.total);
    } catch {
      setTraces([]);
      setTotal(0);
    } finally {
      setTracesLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTraces(tracePage);
  }, [fetchTraces, tracePage]);

  // ── 搜索 ──
  const handleSearch = async () => {
    const q = query.trim();
    if (!q) return;
    setSearching(true);
    setHasSearched(true);
    try {
      const result = await executeQuery({ query: q, search_mode: searchMode, rerank: rerankEnabled });
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

  // ── 打开详情 ──
  const openDetail = (trace: QueryTrace) => {
    setSelectedTrace(trace);
    setDetailModalOpen(true);
  };

  // ── 表格列 ──
  const columns: ColumnsType<QueryTrace> = [
    {
      title: '查询', dataIndex: 'user_query', key: 'user_query', width: 220, ellipsis: true,
      render: (v: string) => (
        <Text ellipsis={{ tooltip: v }} style={{ maxWidth: 220, display: 'block' }}>{v}</Text>
      ),
    },
    {
      title: '延迟', dataIndex: 'total_latency_ms', key: 'total_latency_ms', width: 90,
      sorter: (a, b) => a.total_latency_ms - b.total_latency_ms,
      render: (v: number) => (
        <span style={{ fontVariantNumeric: 'tabular-nums' }}>{fmtMs(v)}</span>
      ),
    },
    {
      title: '缓存', dataIndex: 'cache_hit', key: 'cache_hit', width: 60,
      render: (v: boolean) => v
        ? <Tag color="green" style={{ margin: 0 }}>命中</Tag>
        : <Tag style={{ margin: 0 }}>未命中</Tag>,
    },
    {
      title: '拒绝', dataIndex: 'rejected', key: 'rejected', width: 60,
      render: (v: boolean) => v
        ? <Tag color="red" style={{ margin: 0 }}>是</Tag>
        : <Tag style={{ margin: 0 }}>否</Tag>,
    },
    {
      title: '状态', key: 'status', width: 60,
      render: (_: unknown, r: QueryTrace) => {
        if (r.error) return <Tag icon={<CloseCircleOutlined />} color="error" style={{ margin: 0 }}>误</Tag>;
        if (r.rejected) return <Tag icon={<WarningOutlined />} color="warning" style={{ margin: 0 }}>拒</Tag>;
        return <Tag icon={<CheckCircleOutlined />} color="success" style={{ margin: 0 }}>✓</Tag>;
      },
    },
    {
      title: '时间', dataIndex: 'created_at', key: 'created_at', width: 170,
      render: (v: string) => fmtTime(v),
    },
    {
      title: '详情', key: 'action', width: 60,
      render: (_: unknown, record: QueryTrace) => (
        <Button type="link" size="small" onClick={() => openDetail(record)}>查看</Button>
      ),
    },
  ];

  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      <Title level={3} style={{ marginBottom: 16 }}>AI 知识检索</Title>

      {/* ── Settings Bar ──────────────────────────────────── */}
      <Card size="small" style={{ marginBottom: 20 }} styles={{ body: { padding: '8px 16px' } }}>
        <Flex align="center" justify="space-between" wrap="wrap" gap={8}>
          <Flex align="center" gap={8}>
            <Text strong style={{ fontSize: 13 }}>检索模式</Text>
            <Segmented<SearchMode>
              value={searchMode}
              onChange={setSearchMode}
              options={[
                { value: 'vector_only', label: '仅向量检索' },
                { value: 'hybrid', label: '混合检索' },
              ]}
            />
          </Flex>
          <Flex align="center" gap={8}>
            <Text style={{ fontSize: 13 }}>重排序</Text>
            <Switch checked={rerankEnabled} onChange={setRerankEnabled} size="small" />
          </Flex>
        </Flex>
      </Card>

      {/* ── Search Bar ────────────────────────────────────── */}
      <div style={{ marginBottom: queryResult ? 24 : 32 }}>
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

      <Card
        title="查询历史"
        styles={{ body: { padding: 0 } }}
        extra={
          <Button icon={<ReloadOutlined />} size="small" onClick={() => fetchTraces(tracePage)}>
            刷新
          </Button>
        }
      >
        {tracesLoading && traces.length === 0 ? (
          <Flex justify="center" style={{ padding: 40 }}><Spin /></Flex>
        ) : traces.length === 0 ? (
          <Empty description="暂无查询历史" image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ padding: 40 }} />
        ) : (
          <Table
            columns={columns}
            dataSource={traces}
            rowKey="trace_id"
            loading={tracesLoading}
            scroll={{ x: 800 }}
            pagination={{
              current: tracePage,
              total,
              pageSize: PAGE_SIZE,
              onChange: (p) => { setTracePage(p); fetchTraces(p); },
              showSizeChanger: false,
              size: 'small',
            }}
            locale={{ emptyText: <Empty description="暂无查询历史" /> }}
            size="small"
          />
        )}
      </Card>

      {/* ── 详情 Modal ────────────────────────────────────── */}
      <Modal
        title={selectedTrace ? `Query Trace — ${selectedTrace.trace_id?.slice(0, 8)}...` : 'Query Trace 详情'}
        open={detailModalOpen}
        onCancel={() => { setDetailModalOpen(false); setSelectedTrace(null); }}
        footer={null}
        width={960}
      >
        {selectedTrace && (
          <div>
            {/* 状态 & 基本信息 */}
            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col>
                {selectedTrace.error
                  ? <Tag icon={<CloseCircleOutlined />} color="error" style={{ padding: '4px 12px' }}>错误</Tag>
                  : selectedTrace.rejected
                    ? <Tag icon={<WarningOutlined />} color="warning" style={{ padding: '4px 12px' }}>已拒绝</Tag>
                    : <Tag icon={<CheckCircleOutlined />} color="success" style={{ padding: '4px 12px' }}>正常</Tag>
                }
              </Col>
              <Col flex="auto">
                <Text code style={{ fontSize: 12 }}>Trace ID: {selectedTrace.trace_id}</Text>
              </Col>
            </Row>

            {/* Mode info */}
            {selectedTrace.search_mode && (
              <Row gutter={8} style={{ marginBottom: 16 }}>
                <Col>
                  <Tag color={selectedTrace.search_mode === 'hybrid' ? 'blue' : 'default'}>
                    {selectedTrace.search_mode === 'hybrid' ? '混合检索' : '仅向量检索'}
                  </Tag>
                </Col>
                {selectedTrace.rerank != null && (
                  <Col>
                    <Tag color={selectedTrace.rerank ? 'purple' : 'default'}>
                      重排序: {selectedTrace.rerank ? '启用' : '关闭'}
                    </Tag>
                  </Col>
                )}
              </Row>
            )}

            {/* Pipeline Overview */}
            <h4 style={{ marginBottom: 12 }}>📊 Pipeline Overview</h4>
            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col span={8}>
                <Card size="small">
                  <Statistic title="总延迟" value={fmtMs(selectedTrace.total_latency_ms)} valueStyle={{ fontSize: 16 }} />
                </Card>
              </Col>
              <Col span={8}>
                <Card size="small">
                  <Statistic
                    title="Tokens"
                    value={`${selectedTrace.input_tokens || 0} → ${selectedTrace.output_tokens || 0}`}
                    valueStyle={{ fontSize: 14 }}
                  />
                </Card>
              </Col>
              <Col span={8}>
                <Card size="small">
                  <Statistic
                    title="符合率"
                    value={selectedTrace.faithfulness != null
                      ? `${(selectedTrace.faithfulness * 100).toFixed(0)}%`
                      : '-'}
                    valueStyle={{ fontSize: 16 }}
                  />
                </Card>
              </Col>
            </Row>

            {/* 查询 & 响应 */}
            <Descriptions size="small" column={1} bordered style={{ marginBottom: 16 }}>
              <Descriptions.Item label={<><SearchOutlined /> 查询</>}>
                <Paragraph style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{selectedTrace.user_query}</Paragraph>
              </Descriptions.Item>
              <Descriptions.Item label={<><RobotOutlined /> 响应</>}>
                {selectedTrace.results ? (
                  <Paragraph ellipsis={{ rows: 3, expandable: true, symbol: '展开' }} style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
                    {selectedTrace.results}
                  </Paragraph>
                ) : (
                  <Text type="secondary">—</Text>
                )}
              </Descriptions.Item>
            </Descriptions>

            {/* Top-K 检索结果 */}
            {selectedTrace.top_k_results && selectedTrace.top_k_results.length > 0 && (
              <>
                <Divider style={{ margin: '16px 0' }} />
                <h4 style={{ marginBottom: 12 }}>📄 Top-K 检索结果</h4>
                <Table
                  dataSource={selectedTrace.top_k_results.slice(0, 10)}
                  rowKey={(r: any) => r.chunk_id || Math.random()}
                  pagination={false}
                  size="small"
                  columns={[
                    { title: 'Chunk ID', dataIndex: 'chunk_id', key: 'chunk_id', ellipsis: true, width: 200 },
                    { title: '文本', dataIndex: 'text', key: 'text', ellipsis: true },
                    { title: '评分', dataIndex: 'score', key: 'score', width: 80, render: (v: number) => v?.toFixed(4) },
                  ]}
                />
              </>
            )}

            {/* 元信息 */}
            <Descriptions size="small" column={2} bordered style={{ marginTop: 16 }}>
              <Descriptions.Item label="缓存命中">
                {selectedTrace.cache_hit ? <Tag color="green">是</Tag> : <Tag>否</Tag>}
              </Descriptions.Item>
              <Descriptions.Item label="时间">{fmtTime(selectedTrace.created_at)}</Descriptions.Item>
              <Descriptions.Item label="Input Tokens">{selectedTrace.input_tokens ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="Output Tokens">{selectedTrace.output_tokens ?? '-'}</Descriptions.Item>
              {selectedTrace.rejection_reason && (
                <Descriptions.Item label="拒绝原因" span={2}>
                  <Tag color="red">{selectedTrace.rejection_reason}</Tag>
                </Descriptions.Item>
              )}
              {selectedTrace.error && (
                <Descriptions.Item label="错误" span={2}>
                  <Text type="danger">{selectedTrace.error}</Text>
                </Descriptions.Item>
              )}
            </Descriptions>
          </div>
        )}
      </Modal>
    </div>
  );
}
