/* ============================================================================
 * Knowledge Service — IngestionTraces Ingestion 追踪页面 (G2)
 * ============================================================================ */

import { useState, useEffect } from 'react';
import { Card, Table, Tag, Space, Spin, Alert, Button, Empty } from 'antd';
import { EyeOutlined, ReloadOutlined } from '@ant-design/icons';
import type { IngestionTrace } from '../types';
import type { ColumnsType } from 'antd/es/table';
import WaterfallChart from '../components/WaterfallChart';
import type { Stage } from '../components/WaterfallChart';

// ── Mock 数据 ─────────────────────────────────────────────
const mockTraces: IngestionTrace[] = Array.from({ length: 30 }, (_, i) => {
  const loadMs = Math.floor(Math.random() * 800) + 100;
  const splitMs = Math.floor(Math.random() * 600) + 100;
  const encodeMs = Math.floor(Math.random() * 2000) + 200;
  const indexMs = Math.floor(Math.random() * 1000) + 100;
  const bm25Ms = Math.floor(Math.random() * 500) + 100;
  const totalMs = loadMs + splitMs + encodeMs + indexMs + bm25Ms;

  return {
    trace_id: `trace-ingest-${String(i + 1).padStart(4, '0')}`,
    source_path: `/data/docs/${['employee_handbook', 'compliance', 'technical_spec', 'architecture'][i % 4]}/doc_${i + 1}.${['pdf', 'md', 'html'][i % 3]}`,
    collection: 'default',
    total_latency_ms: totalMs,
    status: (['success', 'success', 'success', 'failed'] as const)[i % 4],
    total_chunks: Math.floor(Math.random() * 60) + 5,
    total_images: 0,
    stages: {
      load: { duration_ms: loadMs, start_ms: 0 },
      split: { duration_ms: splitMs, start_ms: loadMs },
      encode: { duration_ms: encodeMs, start_ms: loadMs + splitMs },
      index: { duration_ms: indexMs, start_ms: loadMs + splitMs + encodeMs },
      bm25: { duration_ms: bm25Ms, start_ms: loadMs + splitMs + encodeMs + indexMs },
    },
    error: i % 4 === 3 ? 'BM25 索引构建超时' : undefined,
    created_at: new Date(Date.now() - i * 7200 * 1000).toISOString(),
  };
});

const statusConfig: Record<string, { color: string; label: string }> = {
  success: { color: 'green', label: '成功' },
  failed: { color: 'red', label: '失败' },
  processing: { color: 'blue', label: '处理中' },
};

export default function IngestionTraces() {
  const [loading, setLoading] = useState(true);
  const [traces, setTraces] = useState<IngestionTrace[]>([]);
  const [selectedTrace, setSelectedTrace] = useState<IngestionTrace | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      setTraces(mockTraces);
      setLoading(false);
    }, 500);
    return () => clearTimeout(timer);
  }, []);

  const waterfallStages = (trace: IngestionTrace): Stage[] => {
    const s = trace.stages as Record<string, { duration_ms: number; start_ms?: number }> | undefined;
    if (!s) return [];
    return [
      { name: 'Load', start_ms: s.load?.start_ms ?? 0, duration_ms: s.load?.duration_ms ?? 0 },
      { name: 'Split', start_ms: s.split?.start_ms ?? 0, duration_ms: s.split?.duration_ms ?? 0 },
      { name: 'Encode', start_ms: s.encode?.start_ms ?? 0, duration_ms: s.encode?.duration_ms ?? 0 },
      { name: 'Index', start_ms: s.index?.start_ms ?? 0, duration_ms: s.index?.duration_ms ?? 0 },
      { name: 'BM25 Index', start_ms: s.bm25?.start_ms ?? 0, duration_ms: s.bm25?.duration_ms ?? 0 },
    ].filter((st) => st.duration_ms > 0);
  };

  const columns: ColumnsType<IngestionTrace> = [
    { title: 'Trace ID', dataIndex: 'trace_id', key: 'trace_id', width: 180, ellipsis: true },
    { title: '文件', dataIndex: 'source_path', key: 'source_path', ellipsis: true, width: 300 },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 80,
      render: (s: string) => {
        const cfg = statusConfig[s];
        return cfg ? <Tag color={cfg.color}>{cfg.label}</Tag> : <Tag>{s}</Tag>;
      },
    },
    {
      title: '耗时', dataIndex: 'total_latency_ms', key: 'total_latency_ms', width: 100,
      render: (v: number) => <span style={{ fontVariantNumeric: 'tabular-nums' }}>{v}ms</span>,
    },
    { title: 'Chunks', dataIndex: 'total_chunks', key: 'total_chunks', width: 80 },
    { title: '时间', dataIndex: 'created_at', key: 'created_at', width: 180 },
    {
      title: '操作', key: 'actions', width: 80,
      render: (_: unknown, record: IngestionTrace) => (
        <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => setSelectedTrace(record)}>
          瀑布图
        </Button>
      ),
    },
  ];

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>Ingestion 追踪</h2>

      {/* 选中 trace 的瀑布图 */}
      {selectedTrace && (
        <Card style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <Space>
              <strong>Trace:</strong> {selectedTrace.trace_id}
              <Tag color={statusConfig[selectedTrace.status]?.color}>
                {statusConfig[selectedTrace.status]?.label}
              </Tag>
              <span style={{ color: '#666' }}>{selectedTrace.source_path}</span>
            </Space>
            <Button size="small" onClick={() => setSelectedTrace(null)}>关闭</Button>
          </div>
          <WaterfallChart
            title="阶段时序瀑布图"
            stages={waterfallStages(selectedTrace)}
            totalDuration={selectedTrace.total_latency_ms}
          />
        </Card>
      )}

      {/* 摄取历史列表 */}
      <Card
        title={`摄取历史 (${traces.length})`}
        extra={
          <Button icon={<ReloadOutlined />} onClick={() => { setLoading(true); setTimeout(() => setLoading(false), 300); }}>
            刷新
          </Button>
        }
      >
        <Table
          columns={columns}
          dataSource={traces}
          rowKey="trace_id"
          loading={loading}
          pagination={{ pageSize: 20, showSizeChanger: true }}
          locale={{ emptyText: <Empty description="暂无摄取历史" /> }}
          size="middle"
        />
      </Card>
    </div>
  );
}
