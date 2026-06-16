import { DeleteOutlined, ReloadOutlined, UploadOutlined, SearchOutlined, EyeOutlined, ExclamationCircleOutlined, InboxOutlined } from '@ant-design/icons';
import { Alert, Button, Card, Col, Divider, Empty, Input, message, Modal, Popconfirm, Row, Select, Space, Spin, Statistic, Table, Tag, Tabs, Upload, Descriptions, Typography } from 'antd';
import { useEffect, useState, useCallback } from 'react';
import type { ColumnsType } from 'antd/es/table';
import type { UploadProps } from 'antd';
import { listDocuments, getDocumentChunks, getBm25Stats, deleteDocument, batchDeleteDocuments } from '../api/documents';
import { uploadFile } from '../api/ingestion';
import type { DocumentInfo, ChunkRecord, Bm25Stat } from '../types';

const categoryOptions = [
  { value: 'employee_handbook', label: '员工手册' },
  { value: 'compliance', label: '合规指南' },
  { value: 'technical_spec', label: '技术规范' },
  { value: 'architecture', label: '架构文档' },
];

const langOptions = [
  { value: 'zh', label: '中文' },
  { value: 'en', label: 'English' },
];

const docTypeOptions = [
  { value: 'pdf', label: 'PDF' },
  { value: 'md', label: 'Markdown' },
  { value: 'html', label: 'HTML' },
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

const statusColors: Record<string, string> = {
  processing: 'processing',
  completed: 'success',
  failed: 'error',
  skipped: 'warning',
};

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

const fmtDur = (ms: number | null | undefined) => {
  if (ms == null) return '—';
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${ms.toFixed(0)}ms`;
};

const fmtTime = (iso: string | null | undefined) => {
  if (!iso) return '-';
  return new Date(iso).toISOString().replace('T', ' ').slice(0, 19);
};

export default function DocumentCenter() {
  const [loading, setLoading] = useState(true);
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [searchText, setSearchText] = useState('');

  // Filters
  const [filterCategory, setFilterCategory] = useState<string | undefined>();
  const [filterLanguage, setFilterLanguage] = useState<string | undefined>();
  const [filterDocType, setFilterDocType] = useState<string | undefined>();

  // Upload
  const [uploading, setUploading] = useState(false);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [fileList, setFileList] = useState<File[]>([]);
  const [selectedCategory, setSelectedCategory] = useState('employee_handbook');
  const [selectedLanguage, setSelectedLanguage] = useState('zh');
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Chunks modal
  const [chunkModalOpen, setChunkModalOpen] = useState(false);
  const [selectedDoc, setSelectedDoc] = useState<DocumentInfo | null>(null);
  const [chunks, setChunks] = useState<ChunkRecord[]>([]);
  const [chunksLoading, setChunksLoading] = useState(false);
  // Ingestion trace modal (uses DocumentInfo directly)
  const [traceModalOpen, setTraceModalOpen] = useState(false);
  const [traceDoc, setTraceDoc] = useState<DocumentInfo | null>(null);
  const [traceStages, setTraceStages] = useState<any[]>([]);
  const [traceLoading, setTraceLoading] = useState(false);
  const [traceChunks, setTraceChunks] = useState<ChunkRecord[]>([]);
  const [bm25StatsMap, setBm25StatsMap] = useState<Record<string, Bm25Stat>>({});

  useEffect(() => {
    if (traceModalOpen && traceDoc) {
      setTraceLoading(true);
      Promise.all([
        getDocumentChunks(traceDoc.id, { page: 1, page_size: 100 }),
        getBm25Stats(traceDoc.id).catch(() => ({ items: [] as Bm25Stat[], total: 0 })),
      ])
        .then(([chunksResult, bm25Result]) => {
          setTraceChunks(chunksResult.items || []);
          const map: Record<string, Bm25Stat> = {};
          for (const stat of bm25Result.items) {
            map[stat.chunk_id] = stat;
          }
          setBm25StatsMap(map);
          setTraceStages([{ stage: 'dummy', duration_ms: null, items: 1, status: 'completed' }]);
        })
        .catch(() => { setTraceChunks([]); setTraceStages([]); setBm25StatsMap({}); })
        .finally(() => setTraceLoading(false));
    } else {
      setTraceChunks([]);
      setTraceStages([]);
      setBm25StatsMap({});
    }
  }, [traceModalOpen, traceDoc]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const docResult = await listDocuments({
        category: filterCategory,
        language: filterLanguage,
        doc_type: filterDocType,
        search: searchText || undefined,
        page,
        page_size: pageSize,
      });
      setDocuments(docResult.items);
      setTotal(docResult.total);
    } catch (err: any) {
      message.error('加载数据失败: ' + (err.message || '未知错误'));
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, filterCategory, filterLanguage, filterDocType, searchText]);

  useEffect(() => { fetchData(); }, [fetchData]);

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

  const openTraceModal = (doc: DocumentInfo) => {
    setTraceDoc(doc);
    setTraceModalOpen(true);
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
    setUploadError(null);
    setUploading(true);
    try {
      await uploadFile(fileList[0], selectedCategory, selectedLanguage);
      message.success('文件已上传并开始处理（处理即弃）');
      setUploadModalOpen(false);
      setFileList([]);
      setUploadError(null);
      fetchData();
    } catch (err: any) {
      const resp = err?.response;
      const detail = resp?.data?.detail || err.message || '请求失败，请检查网络连接';
      setUploadError(detail);
    } finally {
      setUploading(false);
    }
  };

  const openChunkModal = async (doc: DocumentInfo) => {
    setSelectedDoc(doc);
    setChunkModalOpen(true);
    setChunksLoading(true);
    try {
      const result = await getDocumentChunks(doc.id, { page: 1, page_size: 50 });
      setChunks(result.items);
    } catch (err) {
      console.error('Failed to load chunks:', err);
      setChunks([]);
    } finally {
      setChunksLoading(false);
    }
  };

  const filtered = documents;

  const columns: ColumnsType<DocumentInfo> = [
    {
      title: '文件名', dataIndex: 'title', key: 'title', ellipsis: true, width: 260,
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
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 90,
      render: (s: string | null | undefined) => {
        if (!s) return <Tag color="default">—</Tag>;
        const labels: Record<string, string> = { processing: '处理中', completed: '已完成', failed: '失败', skipped: '已跳过' };
        return <Tag color={statusColors[s] || 'default'}>{labels[s] || s}</Tag>;
      },
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
      title: 'Ingestion Trace', key: 'details', width: 80,
      render: (_: unknown, record: DocumentInfo) => (
        <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => openTraceModal(record)}>
          查看
        </Button>
      ),
    },
    {
      title: '删除', key: 'delete', width: 60,
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

      {/* 操作栏 + 筛选 */}
      <Card style={{ marginBottom: 16 }}>
        <Row gutter={[16, 12]} align="middle">
          <Col flex="auto">
            <Space wrap size="middle">
              <Button type="primary" icon={<UploadOutlined />} onClick={() => setUploadModalOpen(true)}>
                上传文件
              </Button>
              {selectedRowKeys.length > 0 && (
                <Button danger icon={<DeleteOutlined />} onClick={handleBatchDelete}>
                  批量删除 ({selectedRowKeys.length})
                </Button>
              )}
            </Space>
          </Col>
          <Col flex="none">
            <Space wrap size="middle">
              <Select
                placeholder="分类"
                allowClear
                style={{ width: 130 }}
                value={filterCategory}
                onChange={(v) => { setFilterCategory(v); setPage(1); }}
                options={categoryOptions}
              />
              <Select
                placeholder="语言"
                allowClear
                style={{ width: 100 }}
                value={filterLanguage}
                onChange={(v) => { setFilterLanguage(v); setPage(1); }}
                options={langOptions}
              />
              <Select
                placeholder="类型"
                allowClear
                style={{ width: 100 }}
                value={filterDocType}
                onChange={(v) => { setFilterDocType(v); setPage(1); }}
                options={docTypeOptions}
              />
              <Input
                placeholder="搜索文件名..."
                prefix={<SearchOutlined />}
                style={{ width: 200 }}
                value={searchText}
                onChange={(e) => setSearchText(e.target.value)}
                allowClear
              />
              <Button icon={<ReloadOutlined />} onClick={fetchData}>刷新</Button>
            </Space>
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
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            pageSizeOptions: ['10', '20', '50'],
            onChange: (p, ps) => { setPage(p); setPageSize(ps); },
          }}
          locale={{ emptyText: <Empty description="暂无文档数据" /> }}
          size="middle"
        />
      </Card>

      {/* 上传 Modal */}
      <Modal
        title="上传文件"
        open={uploadModalOpen}
        onCancel={() => { setUploadModalOpen(false); setFileList([]); setUploadError(null); }}
        onOk={handleUpload}
        confirmLoading={uploading}
        okText="上传并处理"
      >
        {uploadError && (
          <Alert
            message="上传失败"
            description={uploadError}
            type="error"
            showIcon
            closable
            onClose={() => setUploadError(null)}
            style={{ marginBottom: 16 }}
          />
        )}
        <div style={{ marginBottom: 16 }}>
          <Space wrap>
            <Select value={selectedCategory} onChange={setSelectedCategory} style={{ width: 140 }}
              options={categoryOptions} />
            <Select value={selectedLanguage} onChange={setSelectedLanguage} style={{ width: 100 }}
              options={langOptions} />
          </Space>
        </div>
        <Upload.Dragger {...uploadProps}>
          <p className="ant-upload-drag-icon"><InboxOutlined /></p>
          <p className="ant-upload-text">点击或拖拽文件到此处</p>
          <p className="ant-upload-hint">支持 PDF、Markdown、HTML 格式，单文件不超过 50MB。</p>
        </Upload.Dragger>
      </Modal>

      {/* Chunk 详情 Modal */}
      <Modal
        title={selectedDoc ? `Chunk 详情 — ${selectedDoc.title || selectedDoc.source_path}` : 'Chunk 详情'}
        open={chunkModalOpen}
        onCancel={() => setChunkModalOpen(false)}
        footer={null}
        width={800}
      >
        {selectedDoc && (
          <Descriptions column={2} size="small" style={{ marginBottom: 16 }} bordered>
            <Descriptions.Item label="文件">{selectedDoc.source_path}</Descriptions.Item>
            <Descriptions.Item label="总 Chunks">{selectedDoc.chunk_count}</Descriptions.Item>
            <Descriptions.Item label="类型">
              <Tag color={docTypeColors[selectedDoc.doc_type]}>{selectedDoc.doc_type.toUpperCase()}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="语言">{selectedDoc.language === 'zh' ? '中文' : 'English'}</Descriptions.Item>
          </Descriptions>
        )}
        <Table
          columns={[
            { title: '#', dataIndex: 'chunk_index', key: 'chunk_index', width: 60 },
            { title: 'Chunk ID', dataIndex: 'id', key: 'id', ellipsis: true, width: 200 },
            { title: '文本预览', dataIndex: 'text', key: 'text', ellipsis: true },
            { title: 'Token', dataIndex: 'token_count', key: 'token_count', width: 80 },
          ]}
          dataSource={chunks}
          rowKey="id"
          loading={chunksLoading}
          pagination={false}
          size="small"
          locale={{ emptyText: '暂无 Chunk 数据' }}
        />
      </Modal>

      {/* Ingestion Trace Modal */}
      <Modal
        title={traceDoc ? (traceDoc.title || traceDoc.source_path?.split('/').pop() || 'Ingestion Trace') : 'Ingestion Trace'}
        open={traceModalOpen}
        onCancel={() => { setTraceModalOpen(false); setTraceDoc(null); }}
        footer={null}
        width={1100}
      >
        {traceDoc ? (
          <div>
            {/* Pipeline Overview */}
            <h4>📊 Pipeline Overview</h4>
            <Row gutter={16} style={{ marginBottom: 8 }}>
              <Col span={6}><Statistic title="Doc Length" value={traceDoc.file_size ? formatFileSize(traceDoc.file_size) : '—'} valueStyle={{ fontSize: 18 }} /></Col>
              <Col span={6}><Statistic title="Chunks" value={traceDoc.chunk_count ?? '—'} valueStyle={{ fontSize: 18 }} /></Col>
              <Col span={6}><Statistic title="Images" value={traceDoc.image_count ?? 0} valueStyle={{ fontSize: 18 }} /></Col>
              <Col span={6}><Statistic title="Vectors" value={traceDoc.chunk_count ?? '—'} valueStyle={{ fontSize: 18 }} /></Col>
            </Row>
            <Row gutter={16}>
              <Col span={6}><Statistic title="分类" value={categoryLabels[traceDoc.category] || traceDoc.category} valueStyle={{ fontSize: 18 }} /></Col>
              <Col span={6}><Statistic title="语言" value={traceDoc.language === 'zh' ? '中文' : 'English'} valueStyle={{ fontSize: 18 }} /></Col>
              <Col span={6}><Statistic title="类型" value={traceDoc.doc_type.toUpperCase()} valueStyle={{ fontSize: 18 }} /></Col>
              <Col span={6}><Statistic title="上传时间" value={fmtTime(traceDoc.ingested_at)} valueStyle={{ fontSize: 18 }} /></Col>
            </Row>
            {/* Chunk 详情 */}
            <Divider style={{ margin: '24px 0' }} />
            <h4>🧩 Chunk 详情</h4>
            <Spin spinning={traceLoading}>
              <Table
                dataSource={traceChunks}
                rowKey="id"
                pagination={{ pageSize: 10, showSizeChanger: true, pageSizeOptions: ['10', '20', '50'] }}
                size="small"
                scroll={{ x: 900 }}
                columns={[
                  { title: 'Chunk ID', dataIndex: 'id', key: 'id', width: 180, ellipsis: true, render: (v: string) => <Typography.Text code style={{ fontSize: 11 }}>{v.slice(0, 16)}...</Typography.Text> },
                  { title: 'Dense Encoding', key: 'dense', children: [
                  { title: 'Text', dataIndex: 'text', key: 'text', ellipsis: true, width: 300, render: (v: string) => <Typography.Text ellipsis={{ tooltip: v }}>{v.slice(0, 120)}</Typography.Text> },
                    { title: 'Token Count', dataIndex: 'token_count', key: 'token_count', width: 100 },
                  ]},
                  { title: 'Sparse Encoding (BM25)', key: 'sparse', children: [
                    { title: 'Doc Length (terms)', key: 'doc_length', width: 130, render: (_: unknown, r: ChunkRecord) => {
                      const stat = bm25StatsMap[r.id];
                      return <span>{stat ? stat.doc_length : '—'}</span>;
                    }},
                    { title: 'Unique Terms', key: 'unique_terms', width: 110, render: (_: unknown, r: ChunkRecord) => {
                      const stat = bm25StatsMap[r.id];
                      return <span>{stat ? stat.unique_terms : '—'}</span>;
                    }},
                  ]},
                ]}
                locale={{ emptyText: <Empty description="暂无 Chunk 数据" /> }}
              />
            </Spin>
          </div>
        ) : (
          <p style={{ textAlign: 'center', padding: 40, color: '#888' }}>No document data available.</p>
        )}
      </Modal>
    </div>
  );
}
