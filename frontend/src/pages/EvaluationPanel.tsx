import { Card, Row, Col, Statistic, Table, Button } from 'antd';
import { PlayCircleOutlined } from '@ant-design/icons';

const columns = [
  { title: '评估 ID', dataIndex: 'id', key: 'id' },
  { title: '测试集', dataIndex: 'test_set', key: 'test_set' },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at' },
];

export default function EvaluationPanel() {
  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>评估面板</h2>

      <Row gutter={[16, 16]}>
        <Col xs={12} lg={6}><Card><Statistic title="评估运行数" value={0} /></Card></Col>
        <Col xs={12} lg={6}><Card><Statistic title="平均 Hit Rate" value={0} suffix="%" /></Card></Col>
        <Col xs={12} lg={6}><Card><Statistic title="平均 Faithfulness" value={0} suffix="%" /></Card></Col>
      </Row>

      <Card title="评估历史" style={{ marginTop: 16 }} extra={<Button type="primary" icon={<PlayCircleOutlined />}>运行评估</Button>}>
        <Table columns={columns} dataSource={[]} rowKey="id" pagination={{ pageSize: 20 }} />
      </Card>
    </div>
  );
}
