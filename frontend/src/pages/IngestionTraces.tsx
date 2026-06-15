/* ============================================================================
 * Knowledge Service — IngestionTraces 摄取追踪页面 (G2)
 * 由于 ingestion_traces 表在管线 B3 中填充，当前复用 history 端点展示。
 * ============================================================================ */

import { useState, useEffect, useCallback } from 'react';
import { Card, Table, Tag, Alert, Button, Empty, Tooltip } from 'antd';
import { ReloadOutlined, CheckCircleFilled, CloseCircleFilled, LoadingOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { getIngestionHistory } from '../api/ingestion';
import type { IngestionHistoryItem } from '../types';

const statusConfig: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
  completed: { color: 'green', icon: <CheckCircleFilled />, label: '成功' },
  failed: { color: 'red', icon: <CloseCircleFilled />, label: '失败' },
  running: { color: 'blue', icon: <LoadingOutlined />, label: '处理中' },
  processing: { color: 'blue', icon: <LoadingOutlined />, label: '处理中' },
  skipped: { color: 'orange', icon: <CheckCircleFilled />, label: '已跳过' },
};

export default function IngestionTraces() {
  const [loading, setLoading] = useState(true);
  const [traces, setTraces] = useState<IngestionHistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getIngestionHistory({ page, page_size: pageSize });
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

  const columns: ColumnsType<IngestionHistoryItem> = [
    {
      title: '文件', dataIndex: 'file_path', key: 'file_path', ellipsis: true, width: 300,
      render: (v: string) => <Tooltip title={v}><span>{v ? v.split('/').pop() || v : '-'}</span></Tooltip>,
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 90,
      render: (s: string) => {
        const cfg = statusConfig[s] || { color: 'default', icon: null, label: s };
        return <Tag icon={cfg.icon} color={cfg.color}>{cfg.label}</Tag>;
      },
    },
    { title: 'Chunks', dataIndex: 'chunk_count', key: 'chunk_count', width: 70 },
    {
      title: '大小', dataIndex: 'file_size', key: 'file_size', width: 90,
      render: (v: number) => {
        if (v == null) return '-';
        return v > 1048576 ? `${(v / 1048576).toFixed(1)}MB` : `${(v / 1024).toFixed(1)}KB`;
      },
    },
    { title: '集合', dataIndex: 'collection', key: 'collection', width: 80 },
    { title: 'Hash', dataIndex: 'file_hash', key: 'file_hash', width: 80, ellipsis: true,
      render: (v: string) => <Tooltip title={v}><code style={{ fontSize: 11 }}>{v ? v.slice(0, 12) : '-'}</code></Tooltip>,
    },
    {
      title: '时间', dataIndex: 'processed_at', key: 'processed_at', width: 170,
      render: (v: string) => v ? new Date(v).toLocaleString() : '-',
    },
  ];

  if (error) {
    return <Alert type="error" message="加载失败" description={error} showIcon />;
  }

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>Ingestion 追踪</h2>

      <Card
        title={`摄取历史追踪 (${total})`}
        extra={
          <Button icon={<ReloadOutlined />} onClick={fetchData}>刷新</Button>
        }
      >
        <Table
          columns={columns}
          dataSource={traces}
          rowKey="id"
          loading={loading}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            pageSizeOptions: ['10', '20', '50'],
            onChange: (p, ps) => { setPage(p); setPageSize(ps); },
          }}
          locale={{ emptyText: <Empty description="暂无摄取追踪记录" /> }}
          size="middle"
        />
      </Card>
    </div>
  );
}
