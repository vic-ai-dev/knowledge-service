import { PlayCircleOutlined, ReloadOutlined, ExperimentOutlined, CheckCircleFilled, CloseCircleFilled, BarChartOutlined } from '@ant-design/icons';
import { Alert, Button, Card, Col, Empty, message, Modal, Progress, Row, Space, Spin, Statistic, Table, Tag } from 'antd';
import { useEffect, useState } from 'react';
import HistoryChart from '../components/HistoryChart';
import type { ColumnsType } from 'antd/es/table';
import type { EvalResult } from '../types';
// ── Mock 数据 ─────────────────────────────────────────────
const mockResults: EvalResult[] = Array.from({ length: 15 }, (_, i) => ({
  id: `eval-${String(i + 1).padStart(4, '0')}`,
  metrics: {
    hit_rate: 0.72 + Math.random() * 0.25,
    faithfulness: 0.80 + Math.random() * 0.18,
    answer_relevancy: 0.75 + Math.random() * 0.22,
    context_precision: 0.70 + Math.random() * 0.28,
    context_recall: 0.65 + Math.random() * 0.30,
  },
  test_set: ['compliance_qa', 'handbook_qa', 'tech_spec_qa', 'mixed_set'][i % 4],
  backends_used: ['pgvector', 'pgvector+bm25', 'pgvector+bm25+rerank'],
  created_at: new Date(Date.now() - i * 86400 * 1000 * 3).toISOString(),
}));

const hitRateTrend = Array.from({ length: 10 }, (_, i) => ({
  label: `Run ${i + 1}`,
  hit_rate: 0.65 + Math.random() * 0.30,
  faithfulness: 0.75 + Math.random() * 0.20,
}));

const metricLabels: Record<string, string> = {
  hit_rate: 'Hit Rate',
  faithfulness: 'Faithfulness',
  answer_relevancy: 'Answer Relevancy',
  context_precision: 'Context Precision',
  context_recall: 'Context Recall',
};

export default function EvaluationPanel() {
  const [loading, setLoading] = useState(true);
  const [results, setResults] = useState<EvalResult[]>([]);
  const [running, setRunning] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedEval, setSelectedEval] = useState<EvalResult | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      setResults(mockResults);
      setLoading(false);
    }, 600);
    return () => clearTimeout(timer);
  }, []);

  const handleRunEval = async () => {
    setRunning(true);
    message.loading('评估运行中...');
    await new Promise((r) => setTimeout(r, 3000));
    setRunning(false);
    message.success('评估完成');
  };

  // 计算平均指标
  const avgHitRate = results.length > 0
    ? results.reduce((sum, r) => sum + (r.metrics.hit_rate || 0), 0) / results.length
    : 0;
  const avgFaithfulness = results.length > 0
    ? results.reduce((sum, r) => sum + (r.metrics.faithfulness || 0), 0) / results.length
    : 0;
  const totalRuns = results.length;

  const columns: ColumnsType<EvalResult> = [
    { title: '评估 ID', dataIndex: 'id', key: 'id', width: 140, ellipsis: true },
    { title: '测试集', dataIndex: 'test_set', key: 'test_set', width: 160 },
    {
      title: 'Hit Rate', dataIndex: 'metrics', key: 'hit_rate', width: 120,
      render: (m: EvalResult['metrics']) => {
        const v = m.hit_rate || 0;
        return (
          <span>
            <Progress
              percent={Number((v * 100).toFixed(1))}
              size="small"
              format={(pct) => `${pct}%`}
              strokeColor={v > 0.85 ? '#52c41a' : v > 0.7 ? '#fa8c16' : '#f5222d'}
            />
          </span>
        );
      },
    },
    {
      title: 'Faithfulness', dataIndex: 'metrics', key: 'faithfulness', width: 120,
      render: (m: EvalResult['metrics']) => {
        const v = m.faithfulness || 0;
        return (
          <Progress
            percent={Number((v * 100).toFixed(1))}
            size="small"
            format={(pct) => `${pct}%`}
            strokeColor={v > 0.85 ? '#52c41a' : v > 0.7 ? '#fa8c16' : '#f5222d'}
          />
        );
      },
    },
    {
      title: '后端', dataIndex: 'backends_used', key: 'backends_used', width: 200,
      render: (b: string[]) => b.map((s) => <Tag key={s}>{s}</Tag>),
    },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180 },
    {
      title: '操作', key: 'actions', width: 80,
      render: (_: unknown, record: EvalResult) => (
        <Button type="link" size="small" icon={<BarChartOutlined />} onClick={() => { setSelectedEval(record); setModalOpen(true); }}>
          详情
        </Button>
      ),
    },
  ];

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>评估面板</h2>

      {/* 统计卡片 */}
      <Row gutter={[16, 16]}>
        <Col xs={12} lg={6}>
          <Card hoverable>
            <Statistic title="评估运行数" value={totalRuns} prefix={<ExperimentOutlined style={{ color: '#7C3AED' }} />} />
          </Card>
        </Col>
        <Col xs={12} lg={6}>
          <Card hoverable>
            <Statistic
              title="平均 Hit Rate"
              value={(avgHitRate * 100).toFixed(1)}
              suffix="%"
              prefix={<CheckCircleFilled style={{ color: avgHitRate > 0.8 ? '#52c41a' : '#fa8c16' }} />}
              valueStyle={{ color: avgHitRate > 0.8 ? '#389e0d' : '#d46b08' }}
            />
          </Card>
        </Col>
        <Col xs={12} lg={6}>
          <Card hoverable>
            <Statistic
              title="平均 Faithfulness"
              value={(avgFaithfulness * 100).toFixed(1)}
              suffix="%"
              prefix={<CheckCircleFilled style={{ color: avgFaithfulness > 0.85 ? '#52c41a' : '#fa8c16' }} />}
              valueStyle={{ color: avgFaithfulness > 0.85 ? '#389e0d' : '#d46b08' }}
            />
          </Card>
        </Col>
        <Col xs={12} lg={6}>
          <Card hoverable>
            <Statistic title="评估覆盖测试集" value={4} suffix="个" />
          </Card>
        </Col>
      </Row>

      {/* 趋势图 */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={12}>
          <HistoryChart title="Hit Rate 趋势" data={hitRateTrend} dataKey="hit_rate" color="#7C3AED" />
        </Col>
        <Col xs={24} lg={12}>
          <HistoryChart title="Faithfulness 趋势" data={hitRateTrend} dataKey="faithfulness" color="#3B82F6" />
        </Col>
      </Row>

      {/* 评估历史 */}
      <Card
        title="评估历史"
        style={{ marginTop: 16 }}
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => { setLoading(true); setTimeout(() => setLoading(false), 300); }}>
              刷新
            </Button>
            <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleRunEval} loading={running}>
              运行评估
            </Button>
          </Space>
        }
      >
        <Table
          columns={columns}
          dataSource={results}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 20, showSizeChanger: true }}
          locale={{ emptyText: <Empty description="暂无评估记录" /> }}
          size="middle"
        />
      </Card>

      {/* 评估详情 Modal */}
      <Modal
        title={`评估详情 — ${selectedEval?.id}`}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        footer={null}
        width={500}
      >
        {selectedEval && (
          <div>
            <p><strong>测试集:</strong> {selectedEval.test_set}</p>
            <p><strong>后端:</strong> {selectedEval.backends_used.join(' + ')}</p>
            <p><strong>创建时间:</strong> {selectedEval.created_at}</p>
            <div style={{ marginTop: 16 }}>
              {Object.entries(selectedEval.metrics).map(([key, value]) => (
                <div key={key} style={{ marginBottom: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span>{metricLabels[key] || key}</span>
                    <span>{(value * 100).toFixed(1)}%</span>
                  </div>
                  <Progress
                    percent={Number((value * 100).toFixed(1))}
                    size="small"
                    strokeColor={value > 0.85 ? '#52c41a' : value > 0.7 ? '#fa8c16' : '#f5222d'}
                  />
                </div>
              ))}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
