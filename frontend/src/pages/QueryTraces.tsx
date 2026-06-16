/* ============================================================================
 * Knowledge Service — QueryTraces 查询追踪页面 (G9)
 * ============================================================================ */

import {
  ReloadOutlined, ThunderboltOutlined, ClockCircleOutlined,
  DatabaseOutlined, StopOutlined, CheckCircleOutlined,
  CloseCircleOutlined, WarningOutlined, SearchOutlined, RobotOutlined,
} from '@ant-design/icons';
import {
  Button, Card, Col, Descriptions, Empty, Row, Space, Spin,
  Statistic, Table, Tag, Modal, Typography, Divider,
} from 'antd';
import { useEffect, useState, useCallback } from 'react';
import HistoryChart from '../components/HistoryChart';
import type { ColumnsType } from 'antd/es/table';
import type { QueryTrace, QueryMetrics } from '../types';
import { getQueryTraces, getQueryMetrics } from '../api/query';

const { Text, Paragraph } = Typography;

const fmtMs = (ms: number | null | undefined) => {
  if (ms == null) return '—';
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${ms.toFixed(0)}ms`;
};

const fmtTime = (iso: string | null | undefined) => {
  if (!iso) return '-';
  return new Date(iso).toISOString().replace('T', ' ').slice(0, 19);
};

export default function QueryTraces() {
  const [loading, setLoading] = useState(true);
  const [metrics, setMetrics] = useState<QueryMetrics | null>(null);
  const [traces, setTraces] = useState<QueryTrace[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [error, setError] = useState<string | null>(null);
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [selectedTrace, setSelectedTrace] = useState<QueryTrace | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [m, t] = await Promise.all([
        getQueryMetrics(),
        getQueryTraces({ page, page_size: pageSize }),
      ]);
      setMetrics(m);
      setTraces(t.items);
      setTotal(t.total);
    } catch (err: any) {
      setError(err.message || '加载查询追踪数据失败');
      console.error('Failed to load query traces:', err);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const openDetail = (trace: QueryTrace) => {
    setSelectedTrace(trace);
    setDetailModalOpen(true);
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
        <Spin size="large" tip="加载查询数据..." />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 24 }}>
        <Card>
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={`加载失败: ${error}`}
          >
            <Button type="primary" onClick={fetchData} icon={<ReloadOutlined />}>
              重试
            </Button>
          </Empty>
        </Card>
      </div>
    );
  }

  const safeMetrics = metrics || {
    p50_latency_ms: 0,
    p95_latency_ms: 0,
    total_queries: 0,
    total_input_tokens: 0,
    total_output_tokens: 0,
    cache_hit_rate: 0,
    rejection_rate: 0,
    avg_context_precision: 0,
    avg_faithfulness: 0,
    avg_answer_relevancy: 0,
  };

  const columns: ColumnsType<QueryTrace> = [
    {
      title: '查询', dataIndex: 'user_query', key: 'user_query', width: 220, ellipsis: true,
      render: (v: string) => (
        <Text ellipsis={{ tooltip: v }} style={{ maxWidth: 220, display: 'block' }}>
          {v}
        </Text>
      ),
    },
    {
      title: '延迟', dataIndex: 'total_latency_ms', key: 'total_latency_ms', width: 90,
      sorter: (a, b) => a.total_latency_ms - b.total_latency_ms,
      render: (v: number) => {
        const p50 = safeMetrics.p50_latency_ms;
        const p95 = safeMetrics.p95_latency_ms;
        return (
          <span style={{
            fontVariantNumeric: 'tabular-nums',
            color: v > p95 ? '#f5222d' : v > p50 ? '#fa8c16' : '#52c41a',
          }}>
            {fmtMs(v)}
          </span>
        );
      },
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
    <div>
      <h2 style={{ marginBottom: 24 }}>Query 追踪</h2>

      {/* 核心指标卡片 */}
      <Row gutter={[16, 16]}>
        <Col xs={12} lg={6}>
          <Card hoverable>
            <Statistic
              title="P50 延迟"
              value={safeMetrics.p50_latency_ms}
              suffix="ms"
              prefix={<ClockCircleOutlined style={{ color: '#7C3AED' }} />}
              valueStyle={{ color: '#4C1D95' }}
            />
          </Card>
        </Col>
        <Col xs={12} lg={6}>
          <Card hoverable>
            <Statistic
              title="P95 延迟"
              value={safeMetrics.p95_latency_ms}
              suffix="ms"
              prefix={<ThunderboltOutlined style={{ color: '#f5222d' }} />}
              valueStyle={{ color: '#cf1322' }}
            />
          </Card>
        </Col>
        <Col xs={12} lg={6}>
          <Card hoverable>
            <Statistic
              title="缓存命中率"
              value={Number((safeMetrics.cache_hit_rate * 100).toFixed(1))}
              suffix="%"
              prefix={<DatabaseOutlined style={{ color: '#52c41a' }} />}
              precision={1}
              valueStyle={{ color: '#389e0d' }}
            />
          </Card>
        </Col>
        <Col xs={12} lg={3}>
          <Card hoverable>
            <Statistic
              title="拒绝率"
              value={Number((safeMetrics.rejection_rate * 100).toFixed(1))}
              suffix="%"
              prefix={<StopOutlined style={{ color: '#fa8c16' }} />}
              valueStyle={{ color: '#d46b08' }}
            />
          </Card>
        </Col>
        <Col xs={12} lg={3}>
          <Card hoverable>
            <Statistic
              title="总请求"
              value={safeMetrics.total_queries}
              prefix={<CheckCircleOutlined style={{ color: '#3B82F6' }} />}
            />
          </Card>
        </Col>
      </Row>

      {/* Token 用量 */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={12} lg={6}>
          <Card hoverable>
            <Statistic
              title="输入 Token (24h)"
              value={Number((safeMetrics.total_input_tokens / 1_000_000).toFixed(2))}
              suffix="M"
              valueStyle={{ fontSize: 20 }}
            />
          </Card>
        </Col>
        <Col xs={12} lg={6}>
          <Card hoverable>
            <Statistic
              title="输出 Token (24h)"
              value={Number((safeMetrics.total_output_tokens / 1_000_000).toFixed(2))}
              suffix="M"
              valueStyle={{ fontSize: 20 }}
            />
          </Card>
        </Col>
        <Col xs={12} lg={6}>
          <Card hoverable>
            <Statistic
              title="答案符合率"
              value={Number((safeMetrics.avg_context_precision * 100).toFixed(1))}
              suffix="%"
              valueStyle={{ color: '#7C3AED', fontSize: 20 }}
            />
          </Card>
        </Col>
      </Row>

      {/* 延迟趋势图 */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={12}>
          <HistoryChart
            title="P50 / P95 延迟趋势"
            data={traces.length > 0
              ? traces.slice(0, 24).map((t, i) => ({ label: `${i}h`, value: t.total_latency_ms }))
              : [{ label: '暂无数据', value: 0 }]
            }
            dataKey="value"
            color="#7C3AED"
          />
        </Col>
        <Col xs={24} lg={12}>
          <HistoryChart
            title="请求量趋势"
            data={traces.length > 0
              ? traces.slice(0, 24).map((t, i) => ({ label: `${i}h`, value: 1 }))
              : [{ label: '暂无数据', value: 0 }]
            }
            dataKey="value"
            color="#3B82F6"
          />
        </Col>
      </Row>

      {/* 查询历史 */}
      <Card
        title="查询历史"
        style={{ marginTop: 16 }}
        extra={
          <Button icon={<ReloadOutlined />} onClick={fetchData}>刷新</Button>
        }
      >
        <Table
          columns={columns}
          dataSource={traces}
          rowKey="trace_id"
          loading={loading}
          scroll={{ x: 900 }}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            onChange: (p, ps) => { setPage(p); setPageSize(ps); },
          }}
          locale={{ emptyText: <Empty description="暂无查询历史" /> }}
          size="middle"
        />
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
                  <Tag color={selectedTrace.search_mode === 'hybrid' ? 'blue' : 'default'}>{selectedTrace.search_mode === 'hybrid' ? '混合检索' : '仅向量检索'}</Tag>
                </Col>
                <Col>
                  {selectedTrace.rerank != null && (
                    <Tag color={selectedTrace.rerank ? 'purple' : 'default'}>
                      重排序: {selectedTrace.rerank ? '启用' : '关闭'}
                    </Tag>
                  )}
                </Col>
              </Row>
            )}

            {/* Pipeline Overview */}
            <h4>📊 Pipeline Overview</h4>
            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col span={6}>
                <Card size="small">
                  <Statistic title="总延迟" value={fmtMs(selectedTrace.total_latency_ms)} valueStyle={{ fontSize: 16 }} />
                </Card>
              </Col>
              <Col span={6}>
                <Card size="small">
                  <Statistic title="检索耗时" value={fmtMs((selectedTrace.stages as any)?.search_latency_ms)} valueStyle={{ fontSize: 16 }} />
                </Card>
              </Col>
              <Col span={6}>
                <Card size="small">
                  <Statistic title="LLM 耗时" value={fmtMs((selectedTrace.stages as any)?.llm_latency_ms)} valueStyle={{ fontSize: 16 }} />
                </Card>
              </Col>
              <Col span={6}>
                <Card size="small">
                  <Statistic
                    title="tokens"
                    value={`${selectedTrace.input_tokens || 0} → ${selectedTrace.output_tokens || 0}`}
                    valueStyle={{ fontSize: 14 }}
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

            {/* Stage Details */}
            <Divider style={{ margin: '16px 0' }} />
            <h4>🔄 Stage Details</h4>
            <Descriptions size="small" column={2} bordered style={{ marginBottom: 16 }}>
              <Descriptions.Item label="🔍 检索 (Search)">
                耗时: {fmtMs((selectedTrace.stages as any)?.search_latency_ms)}
                &nbsp;| 检索结果: {selectedTrace.top_k_results?.length || 0}
              </Descriptions.Item>
              <Descriptions.Item label="🤖 生成 (LLM)">
                耗时: {fmtMs((selectedTrace.stages as any)?.llm_latency_ms)}
                &nbsp;| Tokens: {selectedTrace.output_tokens || 0}
              </Descriptions.Item>
              {selectedTrace.rejection_reason && (
                <Descriptions.Item label="🚫 拒绝原因" span={2}>
                  <Tag color="red">{selectedTrace.rejection_reason}</Tag>
                </Descriptions.Item>
              )}
              {selectedTrace.error && (
                <Descriptions.Item label="❌ 错误" span={2}>
                  <Text type="danger">{selectedTrace.error}</Text>
                </Descriptions.Item>
              )}
            </Descriptions>

            {/* Top-K 检索结果 */}
            {selectedTrace.top_k_results && selectedTrace.top_k_results.length > 0 && (
              <>
                <Divider style={{ margin: '16px 0' }} />
                <h4>📄 Top-K 检索结果</h4>
                <Table
                  dataSource={selectedTrace.top_k_results.slice(0, 5)}
                  rowKey={(r: any) => r.chunk_id || Math.random()}
                  pagination={false}
                  size="small"
                  columns={[
                    { title: 'Chunk ID', dataIndex: 'chunk_id', key: 'chunk_id', ellipsis: true, width: 180 },
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
              <Descriptions.Item label="符合率">
                {selectedTrace.faithfulness != null ? `${(selectedTrace.faithfulness * 100).toFixed(0)}%` : '-'} / {selectedTrace.answer_relevancy != null ? `${(selectedTrace.answer_relevancy * 100).toFixed(0)}%` : '-'}
              </Descriptions.Item>
              {selectedTrace.category && (
                <Descriptions.Item label="分类">{selectedTrace.category}</Descriptions.Item>
              )}
              {selectedTrace.language && (
                <Descriptions.Item label="语言">{selectedTrace.language === 'zh' ? '中文' : 'English'}</Descriptions.Item>
              )}
            </Descriptions>
          </div>
        )}
      </Modal>
    </div>
  );
}
