import { Card, Table, Tag, Select, Space } from 'antd';

const columns = [
  { title: '文件名', dataIndex: 'source_path', key: 'source_path' },
  { title: '类型', dataIndex: 'doc_type', key: 'doc_type', render: (t: string) => <Tag>{t}</Tag> },
  { title: '分类', dataIndex: 'category', key: 'category' },
  { title: '语言', dataIndex: 'language', key: 'language' },
  { title: 'Chunks', dataIndex: 'chunk_count', key: 'chunk_count' },
];

export default function DataBrowser() {
  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>数据浏览器</h2>

      <Card style={{ marginBottom: 16 }}>
        <Space>
          <Select placeholder="分类筛选" allowClear style={{ width: 160 }}
            options={[
              { value: 'employee_handbook', label: '员工手册' },
              { value: 'compliance', label: '合规指南' },
              { value: 'technical_spec', label: '技术规范' },
              { value: 'architecture', label: '架构文档' },
            ]}
          />
          <Select placeholder="语言筛选" allowClear style={{ width: 120 }}
            options={[{ value: 'zh', label: '中文' }, { value: 'en', label: 'English' }]}
          />
        </Space>
      </Card>

      <Card title="文档列表">
        <Table columns={columns} dataSource={[]} rowKey="id" pagination={{ pageSize: 20 }} />
      </Card>
    </div>
  );
}
