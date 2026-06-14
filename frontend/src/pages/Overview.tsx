import { Card, Row, Col, Statistic, Spin } from 'antd';
import {
  FileTextOutlined,
  DatabaseOutlined,
  CloudUploadOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';

export default function Overview() {
  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>系统总览</h2>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable>
            <Statistic title="文档总数" value={0} prefix={<FileTextOutlined />} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable>
            <Statistic title="Chunk 总数" value={0} prefix={<DatabaseOutlined />} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable>
            <Statistic title="Ingestion 任务" value={0} prefix={<CloudUploadOutlined />} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable>
            <Statistic title="健康状态" value="OK" prefix={<CheckCircleOutlined />} valueStyle={{ color: '#52c41a' }} />
          </Card>
        </Col>
      </Row>

      <Card title="组件配置" style={{ marginTop: 24 }}>
        <p>LLM / Embedding / VectorStore / Reranker 配置将在 E 阶段接入</p>
      </Card>
    </div>
  );
}
