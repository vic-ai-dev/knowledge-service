/* ============================================================================
 * Knowledge Service — EvaluationPanel 评估面板页面 (G11)
 * ============================================================================ */

import { PlayCircleOutlined, ReloadOutlined, ExperimentOutlined, CheckCircleFilled, CloseCircleFilled, BarChartOutlined } from '@ant-design/icons';
import { Button, Card, Col, Empty, message, Modal, Progress, Row, Space, Spin, Statistic, Table, Tag } from 'antd';
import { useEffect, useState, useCallback } from 'react';
import HistoryChart from '../components/HistoryChart';
import type { ColumnsType } from 'antd/es/table';
import type { EvalResult } from '../types';
import { getEvaluationResults, runEvaluation } from '../api/evaluation';

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
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [running, setRunning] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [selectedEval, setSelectedEval] = useState<EvalResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getEvaluationResults({ page, page_size: pageSize });
      setResults(result.items);
      setTotal(result.total);
    } catch (err: any) {
      setError(err.message || '加载评估数据失败');
      console.error('Failed to load evaluation results:', err);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleRunEval = async () => {
    setRunning(true);
    try {
      const result = await runEvaluation({ test_set: 'all' });
      message.success(`评估任务已提交: ${result.task_id}`);
      // 稍后自动刷新
      setTimeout(() => fetchData(), 3000);
    } catch (err: any) {
      message.error('评估启动失败: ' + (err.message || '未知错误'));
    } finally {
      setRunning(false);
    }
  };

  if (loading && results.length === 0) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (error && results.length === 0) {
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

  // 计算平均指标
  const avgHitRate = results.length > 0
    ? results.reduce((sum, r) => sum + (r.metrics.hit_rate || 0), 0) / results.length
    : 0;
  const avgFaithfulness = results.length > 0
    ? results.reduce((sum, r) => sum + (r.metrics.faithfulness || 0), 0) / results.length
    : 0;
  const totalRuns = results.length;

  // 去重测试集
  const testSetCount = new Set(results.map(r => r.test_set)).size;

  const columns: ColumnsType<EvalResult> = [
    { title: '评估 ID', dataIndex: 'id', key: 'id', width: 140, ellipsis: true },
    { title: '测试集', dataIndex: 'test_set', key: 'test_set', width: 160 },
    {
      title: 'Hit Rate', key: 'hit_rate', width: 120,
      render: (_: unknown, record: EvalResult) => {
        const v = record.metrics.hit_rate || 0;
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
      title: 'Faithfulness', key: 'faithfulness', width: 120,
      render: (_: unknown, record: EvalResult) => {
        const v = record.metrics.faithfulness || 0;
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
    {
      title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180,
      render: (v: string) => {
        if (!v) return '-';
        try {
          const d = new Date(v);
          return d.toISOString().slice(0, 19).replace('T', ' ');
        } catch { return v; }
      },
    },
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
              value={Number((avgHitRate * 100).toFixed(1))}
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
              value={Number((avgFaithfulness * 100).toFixed(1))}
              suffix="%"
              prefix={<CheckCircleFilled style={{ color: avgFaithfulness > 0.85 ? '#52c41a' : '#fa8c16' }} />}
              valueStyle={{ color: avgFaithfulness > 0.85 ? '#389e0d' : '#d46b08' }}
            />
          </Card>
        </Col>
        <Col xs={12} lg={6}>
          <Card hoverable>
            <Statistic title="评估覆盖测试集" value={testSetCount} suffix="个" />
          </Card>
        </Col>
      </Row>

      {/* 趋势图 */}
      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} lg={12}>
          <HistoryChart
            title="Hit Rate 趋势"
            data={results.length > 0
              ? results.map((r, i) => ({ label: `Run ${i + 1}`, value: (r.metrics.hit_rate || 0) * 100 }))
              : [{ label: '暂无数据', value: 0 }]
            }
            dataKey="value"
            color="#7C3AED"
          />
        </Col>
        <Col xs={24} lg={12}>
          <HistoryChart
            title="Faithfulness 趋势"
            data={results.length > 0
              ? results.map((r, i) => ({ label: `Run ${i + 1}`, value: (r.metrics.faithfulness || 0) * 100 }))
              : [{ label: '暂无数据', value: 0 }]
            }
            dataKey="value"
            color="#3B82F6"
          />
        </Col>
      </Row>

      {/* 评估历史 */}
      <Card
        title="评估历史"
        style={{ marginTop: 16 }}
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={fetchData}>
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
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            onChange: (p, ps) => { setPage(p); setPageSize(ps); },
          }}
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
            <p><strong>创建时间:</strong> {selectedEval.created_at ? new Date(selectedEval.created_at).toISOString().slice(0, 19).replace('T', ' ') : '-'}</p>
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
