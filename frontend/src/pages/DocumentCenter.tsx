import { DeleteOutlined, ReloadOutlined, UploadOutlined, SearchOutlined, FolderAddOutlined, FolderOpenOutlined, FileTextOutlined, ExclamationCircleOutlined, InboxOutlined } from '@ant-design/icons';
import { Alert, Badge, Button, Card, Col, Empty, Input, message, Modal, Popconfirm, Row, Select, Space, Spin, Statistic, Table, Tag, Upload } from 'antd';
import { useEffect, useState } from 'react';
import type { ColumnsType } from 'antd/es/table';
import type { DocumentInfo, Collection } from '../types';
import type { UploadProps } from 'antd';
// ── Mock 数据 ─────────────────────────────────────────────
const mockDocuments: DocumentInfo[] = Array.from({ length: 52 }, (_, i) => {
  const categories: DocumentInfo['category'][] = ['employee_handbook', 'compliance', 'technical_spec', 'architecture'];
  const languages: DocumentInfo['language'][] = ['zh', 'en'];
  const types: DocumentInfo['doc_type'][] = ['pdf', 'md', 'html'];
  const cat = categories[i % 4];
  const lang = languages[i % 2];
  const type = types[i % 3];
  return {
    id: `doc-${String(i + 1).padStart(4, '0')}`,
    source_path: `/data/docs/${lang}/${cat}/doc_${i + 1}.${type === 'pdf' ? 'pdf' : type === 'md' ? 'md' : 'html'}`,
    title: `文档 ${i + 1}`,
    collection: 'default',
    category: cat,
    language: lang,
    doc_type: type,
    file_size: Math.floor(Math.random() * 10_000_000) + 50_000,
    chunk_count: Math.floor(Math.random() * 80) + 5,
    ingested_at: new Date(Date.now() - Math.random() * 60 * 24 * 3600 * 1000).toISOString(),
    updated_at: new Date(Date.now() - Math.random() * 14 * 24 * 3600 * 1000).toISOString(),
    is_deleted: false,
  };
});

const mockCollections: Collection[] = [
  { id: 'col-1', name: 'default', description: '默认知识库', document_count: 52, chunk_count: 4823, created_at: '2025-01-01T00:00:00Z', updated_at: '2025-06-10T00:00:00Z' },
  { id: 'col-2', name: 'hr_handbook', description: '人力资源手册', document_count: 15, chunk_count: 1240, created_at: '2025-02-15T00:00:00Z', updated_at: '2025-06-08T00:00:00Z' },
  { id: 'col-3', name: 'tech_arch', description: '技术架构文档', document_count: 22, chunk_count: 2150, created_at: '2025-03-01T00:00:00Z', updated_at: '2025-06-12T00:00:00Z' },
];

const categoryLabels: Record<string, string> = {
  employee_handbook: '员工手册',
  compliance: '合规指南',
  technical_spec: '技术规范',
  architecture: '架构文档',
};

const docTypeColors: Record<string, string> = {
  pdf: 'red',
  md: 'blue',
  html: 'orange',
};

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

export default function DocumentCenter() {
  const [loading, setLoading] = useState(true);
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);
  const [searchText, setSearchText] = useState('');
  const [colModalOpen, setColModalOpen] = useState(false);
  const [newColName, setNewColName] = useState('');
  const [newColDesc, setNewColDesc] = useState('');
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [fileList, setFileList] = useState<File[]>([]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDocuments(mockDocuments);
      setCollections(mockCollections);
      setLoading(false);
    }, 500);
    return () => clearTimeout(timer);
  }, []);

  // ── 操作处理函数 ──────────────────────────────────────
  const handleBatchDelete = () => {
    Modal.confirm({
      title: '确认批量删除',
      icon: <ExclamationCircleOutlined />,
      content: `确定要删除选中的 ${selectedRowKeys.length} 个文档吗？（处理即弃，文件将在处理完成后删除）`,
      onOk: () => {
        setDocuments((prev) => prev.filter((d) => !selectedRowKeys.includes(d.id)));
        setSelectedRowKeys([]);
        message.success(`已删除 ${selectedRowKeys.length} 个文档`);
      },
    });
  };

  const handleDeleteDoc = (id: string) => {
    setDocuments((prev) => prev.filter((d) => d.id !== id));
    message.success('文档已删除（处理即弃）');
  };

  const handleCreateCollection = () => {
    if (!newColName.trim()) {
      message.warning('请输入集合名称');
      return;
    }
    const newCol: Collection = {
      id: `col-${Date.now()}`,
      name: newColName.trim(),
      description: newColDesc.trim(),
      document_count: 0,
      chunk_count: 0,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    setCollections((prev) => [...prev, newCol]);
    setColModalOpen(false);
    setNewColName('');
    setNewColDesc('');
    message.success(`集合 "${newCol.name}" 已创建`);
  };

  const handleDeleteCollection = (name: string) => {
    setCollections((prev) => prev.filter((c) => c.name !== name));
    message.success(`集合 "${name}" 已删除`);
  };

  const handleUpload = async () => {
    if (fileList.length === 0) {
      message.warning('请选择文件');
      return;
    }
    setUploading(true);
    await new Promise((r) => setTimeout(r, 2000));
    message.success('文件已上传并开始处理（处理即弃）');
    setUploadModalOpen(false);
    setFileList([]);
    setUploading(false);
  };

  // ── 筛选与表格 ──────────────────────────────────────
  const filtered = documents.filter((doc) => {
    if (searchText && !doc.source_path.toLowerCase().includes(searchText.toLowerCase()) && !doc.title?.toLowerCase().includes(searchText.toLowerCase())) return false;
    return true;
  });

  const columns: ColumnsType<DocumentInfo> = [
    {
      title: '文件名', dataIndex: 'source_path', key: 'source_path', ellipsis: true, width: 280,
    },
    {
      title: '类型', dataIndex: 'doc_type', key: 'doc_type', width: 80,
      render: (t: string) => <Tag color={docTypeColors[t]}>{t.toUpperCase()}</Tag>,
    },
    {
      title: '分类', dataIndex: 'category', key: 'category', width: 100,
      render: (c: string) => categoryLabels[c] || c,
    },
    {
      title: '语言', dataIndex: 'language', key: 'language', width: 70,
      render: (l: string) => l === 'zh' ? '中文' : 'EN',
    },
    { title: 'Chunks', dataIndex: 'chunk_count', key: 'chunk_count', width: 80 },
    {
      title: '大小', dataIndex: 'file_size', key: 'file_size', width: 100,
      render: (s: number) => formatFileSize(s),
    },
    {
      title: '上传时间', dataIndex: 'ingested_at', key: 'ingested_at', width: 180,
    },
    {
      title: '操作', key: 'actions', width: 80,
      render: (_: unknown, record: DocumentInfo) => (
        <Popconfirm title="确定删除此文档？" description="处理即弃，删除后文件将被清除" onConfirm={() => handleDeleteDoc(record.id)} okText="删除" cancelText="取消">
          <Button size="small" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      ),
    },
  ];

  const uploadProps: UploadProps = {
    multiple: false,
    beforeUpload: (file) => {
      const allowed = ['.pdf', '.md', '.html'];
      const ext = '.' + file.name.split('.').pop()?.toLowerCase();
      if (!allowed.includes(ext)) {
        message.error(`不支持的文件类型: ${ext}，仅支持 PDF/Markdown/HTML`);
        return Upload.LIST_IGNORE;
      }
      if (file.size > 50 * 1024 * 1024) {
        message.error('文件大小不能超过 50MB');
        return Upload.LIST_IGNORE;
      }
      setFileList([file]);
      return false;
    },
    onRemove: () => setFileList([]),
    fileList: fileList.map((f) => ({ uid: f.name, name: f.name, status: 'done' as const })),
    accept: '.pdf,.md,.html',
  };

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>文档中心</h2>

      {/* 操作栏 */}
      <Card style={{ marginBottom: 16 }}>
        <Row gutter={[16, 16]} align="middle">
          <Col flex="auto">
            <Space wrap>
              <Button type="primary" icon={<UploadOutlined />} onClick={() => setUploadModalOpen(true)}>
                上传文件
              </Button>
              <Button icon={<FolderAddOutlined />} onClick={() => setColModalOpen(true)}>
                新建集合
              </Button>
              {selectedRowKeys.length > 0 && (
                <Button danger icon={<DeleteOutlined />} onClick={handleBatchDelete}>
                  批量删除 ({selectedRowKeys.length})
                </Button>
              )}
              <Input
                placeholder="搜索文件名..."
                prefix={<SearchOutlined />}
                style={{ width: 240 }}
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                allowClear
              />
            </Space>
          </Col>
          <Col>
            <Button icon={<ReloadOutlined />} onClick={() => { setLoading(true); setTimeout(() => setLoading(false), 300); }}>
              刷新
            </Button>
          </Col>
        </Row>
      </Card>

      {/* 集合列表 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        {collections.map((col) => (
          <Col xs={24} sm={12} lg={8} key={col.name}>
            <Card
              size="small"
              hoverable
              actions={[
                <Popconfirm title={`删除集合 "${col.name}"？`} onConfirm={() => handleDeleteCollection(col.name)} okText="删除" cancelText="取消">
                  <DeleteOutlined key="delete" style={{ color: '#ff4d4f' }} />
                </Popconfirm>,
              ]}
            >
              <Card.Meta
                avatar={<FolderOpenOutlined style={{ fontSize: 24, color: '#7C3AED' }} />}
                title={col.name}
                description={
                  <div>
                    <p style={{ margin: 0, color: '#666', fontSize: 12 }}>{col.description}</p>
                    <Space style={{ marginTop: 8 }}>
                      <Tag>{col.document_count} 文档</Tag>
                      <Tag>{col.chunk_count} Chunks</Tag>
                    </Space>
                  </div>
                }
              />
            </Card>
          </Col>
        ))}
      </Row>

      {/* 文档表格 */}
      <Card title={`文档库 (${filtered.length})`}>
        <Table
          rowSelection={{
            selectedRowKeys,
            onChange: (keys) => setSelectedRowKeys(keys as string[]),
          }}
          columns={columns}
          dataSource={filtered}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 20, showSizeChanger: true, pageSizeOptions: ['10', '20', '50'] }}
          locale={{ emptyText: <Empty description="暂无文档数据" /> }}
          size="middle"
        />
      </Card>

      {/* 上传 Modal */}
      <Modal
        title="上传文件"
        open={uploadModalOpen}
        onCancel={() => { setUploadModalOpen(false); setFileList([]); }}
        onOk={handleUpload}
        confirmLoading={uploading}
        okText="上传并处理"
      >
        <Upload.Dragger {...uploadProps}>
          <p className="ant-upload-drag-icon"><InboxOutlined /></p>
          <p className="ant-upload-text">点击或拖拽文件到此处</p>
          <p className="ant-upload-hint">
            支持 PDF、Markdown、HTML 格式，单文件不超过 50MB。<br />
            处理即弃：文件上传处理完成后自动删除
          </p>
        </Upload.Dragger>
      </Modal>

      {/* 新建集合 Modal */}
      <Modal
        title="新建集合"
        open={colModalOpen}
        onCancel={() => setColModalOpen(false)}
        onOk={handleCreateCollection}
        okText="创建"
      >
        <div style={{ marginBottom: 16 }}>
          <label style={{ display: 'block', marginBottom: 4, fontWeight: 500 }}>集合名称</label>
          <Input
            placeholder="例如：hr_handbook"
            value={newColName}
            onChange={(e) => setNewColName(e.target.value)}
          />
        </div>
        <div>
          <label style={{ display: 'block', marginBottom: 4, fontWeight: 500 }}>描述（可选）</label>
          <Input.TextArea
            placeholder="集合用途说明"
            value={newColDesc}
            onChange={(e) => setNewColDesc(e.target.value)}
            rows={3}
          />
        </div>
      </Modal>
    </div>
  );
}
