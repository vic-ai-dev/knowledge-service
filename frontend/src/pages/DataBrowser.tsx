/* ============================================================================
 * Knowledge Service — DataBrowser 数据浏览器页面 (G1)
 * ============================================================================ */

import { useState, useEffect, useCallback } from 'react';
import { Card, Table, Tag, Select, Space, Input, Spin, Alert, Modal, Descriptions, Button } from 'antd';
import { SearchOutlined, EyeOutlined } from '@ant-design/icons';
import { listDocuments, getDocumentChunks } from '../api/documents';
import type { DocumentInfo, ChunkRecord } from '../types';
import type { ColumnsType } from 'antd/es/table';

// ── 常量 ──────────────────────────────────────────────────
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

const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

export default function DataBrowser() {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<DocumentInfo[]>([]);
  const [category, setCategory] = useState<string | undefined>();
  const [language, setLanguage] = useState<string | undefined>();
  const [docType, setDocType] = useState<string | undefined>();
  const [searchText, setSearchText] = useState('');
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [chunkModalOpen, setChunkModalOpen] = useState(false);
  const [selectedDoc, setSelectedDoc] = useState<DocumentInfo | null>(null);
  const [chunks, setChunks] = useState<ChunkRecord[]>([]);
  const [chunksLoading, setChunksLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const result = await listDocuments({
        category,
        language,
        doc_type: docType,
        page,
        page_size: pageSize,
      });
      setData(result.items);
      setTotal(result.total);
    } catch (err: any) {
      console.error('Failed to load documents:', err);
    } finally {
      setLoading(false);
    }
  }, [category, language, docType, page, pageSize]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const filtered = data.filter((doc) => {
    if (category && doc.category !== category) return false;
    if (language && doc.language !== language) return false;
    if (docType && doc.doc_type !== docType) return false;
    if (searchText && !doc.source_path.toLowerCase().includes(searchText.toLowerCase()) && !doc.title?.toLowerCase().includes(searchText.toLowerCase())) return false;
    return true;
  });

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

  const columns: ColumnsType<DocumentInfo> = [
    { title: '文件名', dataIndex: 'source_path', key: 'source_path', ellipsis: true, width: 280 },
    {
      title: '标题', dataIndex: 'title', key: 'title', ellipsis: true, width: 160,
    },
    {
      title: '类型', dataIndex: 'doc_type', key: 'doc_type', width: 80,
      render: (t: string) => <Tag color={docTypeColors[t]}>{t.toUpperCase()}</Tag>,
    },
    {
      title: '分类', dataIndex: 'category', key: 'category', width: 120,
      render: (c: string) => categoryLabels[c] || c,
    },
    {
      title: '语言', dataIndex: 'language', key: 'language', width: 80,
      render: (l: string) => l === 'zh' ? '中文' : 'English',
    },
    { title: 'Chunks', dataIndex: 'chunk_count', key: 'chunk_count', width: 80 },
    {
      title: '大小', dataIndex: 'file_size', key: 'file_size', width: 100,
      render: (s: number) => formatFileSize(s),
    },
    {
      title: '操作', key: 'actions', width: 80,
      render: (_: unknown, record: DocumentInfo) => (
        <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => openChunkModal(record)}>
          Chunks
        </Button>
      ),
    },
  ];

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>数据浏览器</h2>

      {/* 筛选栏 */}
      <Card style={{ marginBottom: 16 }} bodyStyle={{ paddingBottom: 8 }}>
        <Space wrap size="middle">
          <Select
            placeholder="分类筛选"
            allowClear
            style={{ width: 160 }}
            value={category}
            onChange={(v) => { setCategory(v); setPage(1); }}
            options={categoryOptions}
          />
          <Select
            placeholder="语言筛选"
            allowClear
            style={{ width: 120 }}
            value={language}
            onChange={(v) => { setLanguage(v); setPage(1); }}
            options={langOptions}
          />
          <Select
            placeholder="文件类型"
            allowClear
            style={{ width: 120 }}
            value={docType}
            onChange={(v) => { setDocType(v); setPage(1); }}
            options={docTypeOptions}
          />
          <Input
            placeholder="搜索文件名或标题..."
            prefix={<SearchOutlined />}
            style={{ width: 260 }}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            allowClear
          />
        </Space>
      </Card>

      {/* 文档列表 */}
      <Card title={`文档列表 (${filtered.length})`}>
        <Table
          columns={columns}
          dataSource={filtered}
          rowKey="id"
          loading={loading}
          pagination={{ current: page, pageSize, total, showSizeChanger: true, pageSizeOptions: ['10', '20', '50'], onChange: (p, ps) => { setPage(p); setPageSize(ps); } }}
          locale={{ emptyText: '暂无文档数据' }}
          size="middle"
        />
      </Card>

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
            { title: 'Chunk ID', dataIndex: 'id', key: 'id', ellipsis: true, width: 180 },
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
    </div>
  );
}
