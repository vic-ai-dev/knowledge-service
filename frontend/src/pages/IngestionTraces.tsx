/* ============================================================================
 * Knowledge Service — IngestionTraces Ingestion 追踪页面 (G2)
 * ============================================================================ */

import { useState, useEffect, useCallback } from 'react';
import { Card, Table, Tag, Space, Spin, Alert, Button, Empty } from 'antd';
import { EyeOutlined, ReloadOutlined } from '@ant-design/icons';
import type { IngestionTrace } from '../types';
import type { ColumnsType } from 'antd/es/table';
import { getIngestionTraces, getIngestionTraceDetail } from '../api/ingestion';
import WaterfallChart from '../components/WaterfallChart';
import type { Stage } from '../components/WaterfallChart';

const statusConfig: Record<string, { color: string; label: string }> = {
  success: { color: 'green', label: '成功' },
  failed: { color: 'red', label: '失败' },
  processing: { color: 'blue', label: '处理中' },
};

export default function IngestionTraces() {
  const [loading, setLoading] = useState(true);
  const [traces, setTraces] = useState<IngestionTrace[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [error, setError] = useState<string | null>(null);
  const [selectedTrace, setSelectedTrace] = useState<IngestionTrace | null>(null);
  const [traceLoading, setTraceLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getIngestionTraces({ page, page_size: pageSize });
      setTraces(result.items);
      setTotal(result.total);
    } catch (err: any) {
      setError(err.message || '加载摄取追踪失败');
      console.error('Failed to load ingestion traces:', err);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleViewDetail = async (trace: IngestionTrace) => {
    setSelectedTrace(trace);
    setTraceLoading(true);
    try {
      const detail = await getIngestionTraceDetail(trace.trace_id);
      setSelectedTrace(detail);
    } catch (err) {
      console.error('Failed to load trace detail:', err);
    } finally {
      setTraceLoading(false);
    }
  };

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
        <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => handleViewDetail(record)}>
          瀑布图
        </Button>
      ),
    },
  ];

  if (error) {
    return <Alert type="error" message="加载失败" description={error} showIcon />;
  }

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
          {traceLoading ? (
            <div style={{ textAlign: 'center', padding: 40 }}><Spin /></div>
          ) : (
            <WaterfallChart
              title="阶段时序瀑布图"
              stages={waterfallStages(selectedTrace)}
              totalDuration={selectedTrace.total_latency_ms}
            />
          )}
        </Card>
      )}

      {/* 摄取历史列表 */}
      <Card
        title={`摄取历史 (${total})`}
        extra={
          <Button icon={<ReloadOutlined />} onClick={fetchData}>刷新</Button>
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
            pageSizeOptions: ['10', '20', '50'],
            onChange: (p, ps) => { setPage(p); setPageSize(ps); },
          }}
          locale={{ emptyText: <Empty description="暂无摄取历史" /> }}
          size="middle"
        />
      </Card>
    </div>
  );
}
