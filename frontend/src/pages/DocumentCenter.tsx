import { Card, Table, Button, Space, Tag, Upload } from 'antd';
import { UploadOutlined, DeleteOutlined, ReloadOutlined } from '@ant-design/icons';

const columns = [
  { title: '文件名', dataIndex: 'source_path', key: 'source_path' },
  { title: '类型', dataIndex: 'doc_type', key: 'doc_type', render: (t: string) => <Tag>{t}</Tag> },
  { title: '分类', dataIndex: 'category', key: 'category' },
  { title: '语言', dataIndex: 'language', key: 'language' },
  { title: 'Chunks', dataIndex: 'chunk_count', key: 'chunk_count' },
  { title: '操作', key: 'actions', render: () => <Button size="small" danger icon={<DeleteOutlined />} /> },
];

export default function DocumentCenter() {
  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>文档中心</h2>

      <Card style={{ marginBottom: 16 }}>
        <Space>
          <Upload>
            <Button type="primary" icon={<UploadOutlined />}>上传文件</Button>
          </Upload>
          <Button icon={<ReloadOutlined />}>刷新</Button>
        </Space>
      </Card>

      <Card title="文档库">
        <Table
          columns={columns}
          dataSource={[]}
          rowKey="id"
          pagination={{ pageSize: 20 }}
        />
      </Card>
    </div>
  );
}
