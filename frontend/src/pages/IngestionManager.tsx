import { Card, Upload, Table, Button, Tag, Progress } from 'antd';
import { InboxOutlined, PlayCircleOutlined } from '@ant-design/icons';

const { Dragger } = Upload;

const columns = [
  { title: '文件', dataIndex: 'source_path', key: 'source_path' },
  { title: '状态', dataIndex: 'status', key: 'status', render: (s: string) => <Tag color={s === 'success' ? 'green' : s === 'failed' ? 'red' : 'blue'}>{s}</Tag> },
  { title: 'Chunks', dataIndex: 'total_chunks', key: 'total_chunks' },
  { title: '时间', dataIndex: 'created_at', key: 'created_at' },
];

export default function IngestionManager() {
  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>Ingestion 管理</h2>

      <Card style={{ marginBottom: 16 }}>
        <Dragger>
          <p className="ant-upload-drag-icon"><InboxOutlined /></p>
          <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
          <p className="ant-upload-hint">支持 PDF、Markdown、HTML 格式</p>
        </Dragger>
      </Card>

      <Card title="摄取记录">
        <Table columns={columns} dataSource={[]} rowKey="run_id" pagination={{ pageSize: 20 }} />
      </Card>
    </div>
  );
}
