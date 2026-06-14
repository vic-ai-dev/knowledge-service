import { ReloadOutlined, ThunderboltOutlined, ClockCircleOutlined, DatabaseOutlined, StopOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { Alert, Button, Card, Col, Descriptions, Empty, Row, Space, Spin, Statistic, Table, Tag } from 'antd';
import { useEffect, useState } from 'react';
import HistoryChart from '../components/HistoryChart';
import type { ColumnsType } from 'antd/es/table';
import type { QueryTrace, QueryMetrics } from '../types';
// ── Mock 数据 ─────────────────────────────────────────────
const mockMetrics: QueryMetrics = {
  p50_latency: 2340,
  p95_latency: 8120,
  total_requests: 1567,
  input_tokens: 4_567_890,
  output_tokens: 1_234_567,
  cache_hit_rate: 0.68,
  rejection_rate: 0.035,
  avg_compliance_score: 0.94,
  period: '24h',
};

const mockTraces: QueryTrace[] = Array.from({ length: 40 }, (_, i) => ({
  trace_id: `trace-query-${String(i + 1).padStart(4, '0')}`,
  user_query: [
    '公司年假政策是什么？',
    '如何提交报销申请？',
    'What is the technical architecture?',
    '数据加密标准有哪些要求？',
    'Code review guidelines for Node.js services',
    '合规培训的截止日期是什么时候？',
    'Explain the microservices deployment process',
    '加班费怎么计算？',
    '系统可用性 SLA 是多少？',
    'Employee onboarding checklist',
  ][i % 10],
  collection: 'default',
  total_latency_ms: Math.floor(Math.random() * 8000) + 500,
  input_tokens: Math.floor(Math.random() * 1500) + 200,
  output_tokens: Math.floor(Math.random() * 500) + 50,
  total_tokens: 0,
  cache_hit: i % 7 === 0,
  rejected: i % 15 === 0,
  rejection_reason: i % 15 === 0 ? '检测到越狱提示注入攻击' : undefined,
  compliance_score: 0.85 + Math.random() * 0.15,
  stages: {
    retrieval: { duration_ms: Math.floor(Math.random() * 3000) + 200 },
    rerank: { duration_ms: Math.floor(Math.random() * 1000) + 100 },
    generation: { duration_ms: Math.floor(Math.random() * 4000) + 500 },
  },
  created_at: new Date(Date.now() - i * 1800 * 1000).toISOString(),
}));

const latencyData = Array.from({ length: 24 }, (_, i) => ({
  label: `${i}:00`,
  p50: Math.floor(Math.random() * 3000) + 1000,
  p95: Math.floor(Math.random() * 5000) + 3000,
  count: Math.floor(Math.random() * 80) + 10,
}));

export default function QueryTraces() {
  const [loading, setLoading] = useState(true);
  const [metrics, setMetrics] = useState<QueryMetrics | null>(null);
  const [traces, setTraces] = useState<QueryTrace[]>([]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setMetrics(mockMetrics);
      setTraces(mockTraces);
      setLoading(false);
    }, 600);
    return () => clearTimeout(timer);
  }, []);

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
        <Spin size="large" tip="加载查询数据..." />
      </div>
    );
  }

  const columns: ColumnsType<QueryTrace> = [
    { title: 'Trace ID', dataIndex: 'trace_id', key: 'trace_id', width: 180, ellipsis: true },
    { title: '查询', dataIndex: 'user_query', key: 'user_query', width: 260, ellipsis: true },
    {
      title: '延迟', dataIndex: 'total_latency_ms', key: 'total_latency_ms', width: 100, sorter: (a, b) => a.total_latency_ms - b.total_latency_ms,
      render: (v: number) => (
        <span style={{
          fontVariantNumeric: 'tabular-nums',
          color: v > metrics!.p95_latency ? '#f5222d' : v > metrics!.p50_latency ? '#fa8c16' : '#52c41a',
        }}>
          {v}ms
        </span>
      ),
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

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>Query 追踪</h2>

      {/* 核心指标卡片 */}
      <Row gutter={[16, 16]}>
        <Col xs={12} lg={6}>
          <Card hoverable>
            <Statistic
              title="P50 延迟"
              value={metrics!.p50_latency}
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
              value={metrics!.p95_latency}
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
              value={(metrics!.cache_hit_rate * 100).toFixed(1)}
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
              value={(metrics!.rejection_rate * 100).toFixed(1)}
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
              value={metrics!.total_requests}
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
              value={(metrics!.input_tokens / 1_000_000).toFixed(2)}
              suffix="M"
              valueStyle={{ fontSize: 20 }}
            />
          </Card>
        </Col>
        <Col xs={12} lg={6}>
          <Card hoverable>
            <Statistic
              title="输出 Token (24h)"
              value={(metrics!.output_tokens / 1_000_000).toFixed(2)}
              suffix="M"
              valueStyle={{ fontSize: 20 }}
            />
          </Card>
        </Col>
        <Col xs={12} lg={6}>
          <Card hoverable>
            <Statistic
              title="答案符合率"
              value={(metrics!.avg_compliance_score * 100).toFixed(1)}
              suffix="%"
              valueStyle={{ color: '#7C3AED', fontSize: 20 }}
            />
          </Card>
        </Col>
      </Row>

      {/* 延迟趋势图 */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={12}>
          <HistoryChart title="P50 / P95 延迟趋势" data={latencyData} dataKey="p50" color="#7C3AED" />
        </Col>
        <Col xs={24} lg={12}>
          <HistoryChart title="请求量趋势" data={latencyData} dataKey="count" color="#3B82F6" />
        </Col>
      </Row>

      {/* 查询历史 */}
      <Card title="查询历史" style={{ marginTop: 16 }}>
        <Table
          columns={columns}
          dataSource={traces}
          rowKey="trace_id"
          pagination={{ pageSize: 20, showSizeChanger: true }}
          locale={{ emptyText: <Empty description="暂无查询历史" /> }}
          size="middle"
          expandable={{
            expandedRowRender: (record) => (
              <Descriptions size="small" column={2} bordered style={{ padding: 8 }}>
                <Descriptions.Item label="Input Tokens">{record.input_tokens}</Descriptions.Item>
                <Descriptions.Item label="Output Tokens">{record.output_tokens}</Descriptions.Item>
                <Descriptions.Item label="检索耗时">{record.stages?.retrieval?.duration_ms || '-'}ms</Descriptions.Item>
                <Descriptions.Item label="重排序耗时">{record.stages?.rerank?.duration_ms || '-'}ms</Descriptions.Item>
                <Descriptions.Item label="生成耗时">{record.stages?.generation?.duration_ms || '-'}ms</Descriptions.Item>
                <Descriptions.Item label="符合率">{record.compliance_score ? `${(record.compliance_score * 100).toFixed(0)}%` : '-'}</Descriptions.Item>
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
