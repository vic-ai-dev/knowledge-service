import { Card, Row, Col, Statistic, Table, Tag } from 'antd';

const columns = [
  { title: 'Trace ID', dataIndex: 'trace_id', key: 'trace_id' },
  { title: '查询', dataIndex: 'user_query', key: 'user_query', ellipsis: true },
  { title: '耗时 (ms)', dataIndex: 'total_latency_ms', key: 'total_latency_ms' },
  { title: '缓存', dataIndex: 'cache_hit', key: 'cache_hit', render: (v: boolean) => v ? <Tag color="green">命中</Tag> : <Tag>未命中</Tag> },
  { title: '拒绝', dataIndex: 'rejected', key: 'rejected', render: (v: boolean) => v ? <Tag color="red">是</Tag> : <Tag>否</Tag> },
];

export default function QueryTraces() {
  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>Query 追踪</h2>

      <Row gutter={[16, 16]}>
        <Col xs={12} lg={6}><Card><Statistic title="P50 延迟" value={0} suffix="ms" /></Card></Col>
        <Col xs={12} lg={6}><Card><Statistic title="P95 延迟" value={0} suffix="ms" /></Card></Col>
        <Col xs={12} lg={6}><Card><Statistic title="缓存命中率" value={0} suffix="%" /></Card></Col>
        <Col xs={12} lg={6}><Card><Statistic title="拒绝率" value={0} suffix="%" /></Card></Col>
      </Row>

      <Card title="查询历史" style={{ marginTop: 16 }}>
        <Table columns={columns} dataSource={[]} rowKey="trace_id" pagination={{ pageSize: 20 }} />
      </Card>
    </div>
  );
}
