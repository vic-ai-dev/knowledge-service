import { DeleteOutlined, ReloadOutlined, UploadOutlined, SearchOutlined, FileTextOutlined, ExclamationCircleOutlined, InboxOutlined } from '@ant-design/icons';
import { Alert, Badge, Button, Card, Col, Empty, Input, message, Modal, Popconfirm, Row, Select, Space, Spin, Statistic, Table, Tag, Upload } from 'antd';
import { useEffect, useState, useCallback } from 'react';
import type { ColumnsType } from 'antd/es/table';
import { listDocuments, deleteDocument, batchDeleteDocuments } from '../api/documents';
import { uploadFile } from '../api/ingestion';
import type { DocumentInfo } from '../types';
import type { UploadProps } from 'antd';
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
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [searchText, setSearchText] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [fileList, setFileList] = useState<File[]>([]);
  const [selectedCategory, setSelectedCategory] = useState('employee_handbook');
  const [selectedLanguage, setSelectedLanguage] = useState('zh');

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const docResult = await listDocuments({ page, page_size: pageSize });
      setDocuments(docResult.items);
      setTotal(docResult.total);
    } catch (err: any) {
      message.error('加载数据失败: ' + (err.message || '未知错误'));
    } finally {
      setLoading(false);
    }
  }, [page, pageSize]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // ── 操作处理函数 ──────────────────────────────────────
  const handleBatchDelete = () => {
    Modal.confirm({
      title: '确认批量删除',
      icon: <ExclamationCircleOutlined />,
      content: `确定要删除选中的 ${selectedRowKeys.length} 个文档吗？（处理即弃，文件将在处理完成后删除）`,
      onOk: async () => {
        try {
          await batchDeleteDocuments(selectedRowKeys);
          message.success(`已删除 ${selectedRowKeys.length} 个文档`);
          setSelectedRowKeys([]);
          fetchData();
        } catch (err: any) {
          message.error('批量删除失败: ' + (err.message || '未知错误'));
        }
      },
    });
  };

  const handleDeleteDoc = async (id: string) => {
    try {
      await deleteDocument(id);
      message.success('文档已删除（处理即弃）');
      fetchData();
    } catch (err: any) {
      message.error('删除失败: ' + (err.message || '未知错误'));
    }
  };

  const handleUpload = async () => {
    if (fileList.length === 0) {
      message.warning('请选择文件');
      return;
    }
    setUploading(true);
    try {
      await uploadFile(fileList[0], selectedCategory, selectedLanguage);
      message.success('文件已上传并开始处理（处理即弃）');
      setUploadModalOpen(false);
      setFileList([]);
      fetchData();
    } catch (err: any) {
      message.error('上传失败: ' + (err.message || '未知错误'));
    } finally {
      setUploading(false);
    }
  };

  // ── 筛选与表格 ──────────────────────────────────────
  const filtered = documents.filter((doc) => {
    if (searchText && !doc.source_path.toLowerCase().includes(searchText.toLowerCase()) && !doc.title?.toLowerCase().includes(searchText.toLowerCase())) return false;
    return true;
  });

  const columns: ColumnsType<DocumentInfo> = [
    {
      title: '文件名', dataIndex: 'title', key: 'title', ellipsis: true, width: 280,
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
      render: (t: string | null) => {
        if (!t) return '-';
        const d = new Date(t);
        const pad = (n: number) => String(n).padStart(2, '0');
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
      },
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
            <Button icon={<ReloadOutlined />} onClick={fetchData}>
              刷新
            </Button>
          </Col>
        </Row>
      </Card>

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
          pagination={{ current: page, pageSize, total, showSizeChanger: true, pageSizeOptions: ['10', '20', '50'], onChange: (p, ps) => { setPage(p); setPageSize(ps); } }}
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
        <div style={{ marginBottom: 16 }}>
          <Space wrap>
            <Select
              value={selectedCategory}
              onChange={setSelectedCategory}
              style={{ width: 140 }}
              options={[
                { value: 'employee_handbook', label: '员工手册' },
                { value: 'compliance', label: '合规指南' },
                { value: 'technical_spec', label: '技术规范' },
                { value: 'architecture', label: '架构文档' },
              ]}
            />
            <Select
              value={selectedLanguage}
              onChange={setSelectedLanguage}
              style={{ width: 100 }}
              options={[
                { value: 'zh', label: '中文' },
                { value: 'en', label: 'English' },
              ]}
            />
          </Space>
        </div>
        <Upload.Dragger {...uploadProps}>
          <p className="ant-upload-drag-icon"><InboxOutlined /></p>
          <p className="ant-upload-text">点击或拖拽文件到此处</p>
          <p className="ant-upload-hint">
            支持 PDF、Markdown、HTML 格式，单文件不超过 50MB。<br />
            处理即弃：文件上传处理完成后自动删除
          </p>
        </Upload.Dragger>
      </Modal>

