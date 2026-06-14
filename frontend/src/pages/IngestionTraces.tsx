import { Card, Table, Tag } from 'antd';

const columns = [
  { title: 'Trace ID', dataIndex: 'trace_id', key: 'trace_id' },
  { title: '文件', dataIndex: 'source_path', key: 'source_path' },
  { title: '状态', dataIndex: 'status', key: 'status', render: (s: string) => <Tag color={s === 'success' ? 'green' : 'red'}>{s}</Tag> },
  { title: '耗时 (ms)', dataIndex: 'total_latency_ms', key: 'total_latency_ms' },
  { title: 'Chunks', dataIndex: 'total_chunks', key: 'total_chunks' },
];

export default function IngestionTraces() {
  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>Ingestion 追踪</h2>
      <Card title="摄取历史">
        <p style={{ color: '#999', marginBottom: 16 }}>阶段瀑布图将在阶段 E 完成后展示</p>
        <Table columns={columns} dataSource={[]} rowKey="trace_id" pagination={{ pageSize: 20 }} />
      </Card>
    </div>
  );
}
