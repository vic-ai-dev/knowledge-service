/* ============================================================================
 * Knowledge Service — QueryTraces 查询追踪页面 (G9)
 * ============================================================================ */

import { ReloadOutlined, ThunderboltOutlined, ClockCircleOutlined, DatabaseOutlined, StopOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { Button, Card, Col, Descriptions, Empty, Row, Space, Spin, Statistic, Table, Tag } from 'antd';
import { useEffect, useState, useCallback } from 'react';
import HistoryChart from '../components/HistoryChart';
import type { ColumnsType } from 'antd/es/table';
import type { QueryTrace, QueryMetrics } from '../types';
import { getQueryTraces, getQueryMetrics } from '../api/query';

export default function QueryTraces() {
  const [loading, setLoading] = useState(true);
  const [metrics, setMetrics] = useState<QueryMetrics | null>(null);
  const [traces, setTraces] = useState<QueryTrace[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [error, setError] = useState<string | null>(null);

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

  useEffect(() => {
    fetchData();
  }, [fetchData]);

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

  const columns: ColumnsType<QueryTrace> = [
    { title: 'Trace ID', dataIndex: 'trace_id', key: 'trace_id', width: 180, ellipsis: true },
    { title: '查询', dataIndex: 'user_query', key: 'user_query', width: 260, ellipsis: true },
    {
      title: '延迟', dataIndex: 'total_latency_ms', key: 'total_latency_ms', width: 100,
      sorter: (a, b) => a.total_latency_ms - b.total_latency_ms,
      render: (v: number) => {
        const p50 = metrics?.p50_latency_ms ?? 0;
        const p95 = metrics?.p95_latency_ms ?? 0;
        return (
          <span style={{
            fontVariantNumeric: 'tabular-nums',
            color: v > p95 ? '#f5222d' : v > p50 ? '#fa8c16' : '#52c41a',
          }}>
            {v}ms
          </span>
        );
      },
    },
    {
      title: 'Token', key: 'tokens', width: 140,
      render: (_: unknown, r: QueryTrace) => `${r.input_tokens + r.output_tokens}`,
    },
    {
      title: '缓存', dataIndex: 'cache_hit', key: 'cache_hit', width: 70,
      render: (v: boolean) => v
        ? <Tag color="green" style={{ margin: 0 }}>命中</Tag>
        : <Tag style={{ margin: 0 }}>未命中</Tag>,
    },
    {
      title: '拒绝', dataIndex: 'rejected', key: 'rejected', width: 70,
      render: (v: boolean) => v
        ? <Tag color="red" style={{ margin: 0 }}>是</Tag>
        : <Tag style={{ margin: 0 }}>否</Tag>,
    },
    {
      title: '符合率', dataIndex: 'compliance_score', key: 'compliance_score', width: 80,
      render: (v?: number) => v ? `${(v * 100).toFixed(0)}%` : '-',
    },
    { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 180 },
  ];

  const safeMetrics = metrics || {
    p50_latency_ms: 0,
    p95_latency_ms: 0,
    total_queries: 0,
    total_input_tokens: 0,
    total_output_tokens: 0,
    cache_hit_rate: 0,
    rejection_rate: 0,
    avg_compliance_score: 0,
  };

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
              value={Number((safeMetrics.avg_compliance_score * 100).toFixed(1))}
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
              ? traces.slice(0, 24).map((t, i) => ({
                  label: `${i}h`,
                  value: t.total_latency_ms,
                }))
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
              ? traces.slice(0, 24).map((t, i) => ({
                  label: `${i}h`,
                  value: 1,
                }))
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
          <Button icon={<ReloadOutlined />} onClick={fetchData}>
            刷新
          </Button>
        }
      >
        <Table
          columns={columns}
          dataSource={traces}
          rowKey="trace_id"
          loading={loading}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            onChange: (p, ps) => { setPage(p); setPageSize(ps); },
          }}
          locale={{ emptyText: <Empty description="暂无查询历史" /> }}
          size="middle"
          expandable={{
            expandedRowRender: (record) => (
              <Descriptions size="small" column={2} bordered style={{ padding: 8 }}>
                <Descriptions.Item label="Input Tokens">{record.input_tokens}</Descriptions.Item>
                <Descriptions.Item label="Output Tokens">{record.output_tokens}</Descriptions.Item>
                <Descriptions.Item label="检索耗时">
                  {record.stages && (record.stages as any).retrieval?.duration_ms
                    ? `${(record.stages as any).retrieval.duration_ms}ms` : '-'}
                </Descriptions.Item>
                <Descriptions.Item label="重排序耗时">
                  {record.stages && (record.stages as any).rerank?.duration_ms
                    ? `${(record.stages as any).rerank.duration_ms}ms` : '-'}
                </Descriptions.Item>
                <Descriptions.Item label="生成耗时">
                  {record.stages && (record.stages as any).generation?.duration_ms
                    ? `${(record.stages as any).generation.duration_ms}ms` : '-'}
                </Descriptions.Item>
                <Descriptions.Item label="符合率">
                  {record.compliance_score ? `${(record.compliance_score * 100).toFixed(0)}%` : '-'}
                </Descriptions.Item>
                {record.rejection_reason && (
                  <Descriptions.Item label="拒绝原因" span={2}>
                    <Tag color="red">{record.rejection_reason}</Tag>
                  </Descriptions.Item>
                )}
              </Descriptions>
            ),
          }}
        />
      </Card>
    </div>
  );
}
