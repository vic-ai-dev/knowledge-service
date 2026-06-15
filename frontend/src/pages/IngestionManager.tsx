import { InboxOutlined, PlayCircleOutlined, ReloadOutlined, CheckCircleFilled, CloseCircleFilled, LoadingOutlined } from '@ant-design/icons';
import { Alert, Button, Card, message, Modal, Progress, Select, Space, Spin, Table, Tag, Upload } from 'antd';
import { useEffect, useState, useCallback } from 'react';
import type { ColumnsType } from 'antd/es/table';
import { getIngestionHistory, uploadFile } from '../api/ingestion';

import type { UploadProps } from 'antd';
const { Dragger } = Upload;

interface IngestionHistoryItem {
  id: string; file_hash: string; file_path: string; file_size: number;
  status: string; category: string; language: string; doc_type: string;
  chunk_count: number; error_msg: string | null; processed_at: string | null;
}

const statusConfig: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
  completed: { color: 'green', icon: <CheckCircleFilled />, label: '成功' },
  failed: { color: 'red', icon: <CloseCircleFilled />, label: '失败' },
  running: { color: 'blue', icon: <LoadingOutlined />, label: '处理中' },
  skipped: { color: 'orange', icon: <CheckCircleFilled />, label: '已跳过' },
};

export default function IngestionManager() {
  const [loading, setLoading] = useState(true);
  const [history, setHistory] = useState<IngestionHistoryItem[]>([]);
  const [uploading, setUploading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState('employee_handbook');
  const [selectedLanguage, setSelectedLanguage] = useState('zh');
  const [fileList, setFileList] = useState<File[]>([]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const result = await getIngestionHistory({ page, page_size: pageSize });
      setHistory(result.items);
      setTotal(result.total);
    } catch (err: any) {
      console.error('Failed to load ingestion history:', err);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleRunIngestion = async (trace: IngestionHistoryItem) => {
    message.info(`重新摄取: ${trace.file_path}`);
    // TODO: 触发 Ingestion Pipeline 重新处理
  };

  const handleUpload = async () => {
    if (fileList.length === 0) {
      message.warning('请选择文件');
      return;
    }
    setUploading(true);
    try {
      await uploadFile(fileList[0], selectedCategory, selectedLanguage);
      message.success('文件已提交摄取');
      setUploadModalOpen(false);
      setFileList([]);
      fetchData();
    } catch (err: any) {
      message.error('上传失败: ' + (err.message || '未知错误'));
    } finally {
      setUploading(false);
    }
  };

  const columns: ColumnsType<IngestionHistoryItem> = [
    {
      title: '文件', dataIndex: 'file_path', key: 'source_path', ellipsis: true, width: 300,
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 100,
      render: (s: string) => {
        const cfg = statusConfig[s] || { color: 'default', icon: null, label: s };
        return <Tag icon={cfg.icon} color={cfg.color}>{cfg.label}</Tag>;
      },
    },
    {
      title: '类型', dataIndex: 'doc_type', key: 'doc_type', width: 80,
      render: (v: string) => <Tag>{v}</Tag>,
    },
    {
      title: '分类', dataIndex: 'category', key: 'category', width: 100,
      render: (v: string) => {
        const m: Record<string, string> = {
          employee_handbook: '员工手册', compliance: '合规指南',
          technical_spec: '技术规范', architecture: '架构文档',
        };
        return m[v] || v;
      },
    },
    { title: 'Chunks', dataIndex: 'chunk_count', key: 'chunk_count', width: 80 },
    {
      title: '大小', dataIndex: 'file_size', key: 'file_size', width: 100,
      render: (v: number) => v ? `${(v / 1024).toFixed(1)}KB` : '-',
    },
    { title: '时间', dataIndex: 'processed_at', key: 'processed_at', width: 180 },
    {
      title: '操作', key: 'actions', width: 120,
      render: (_: unknown, record: IngestionHistoryItem) => (
        <Space>
          {record.status === 'failed' && (
            <Button type="link" size="small" onClick={() => handleRunIngestion(record)}>
              重试
            </Button>
          )}
          {record.status === 'completed' && (
            <Button type="link" size="small" onClick={() => handleRunIngestion(record)}>
              重新摄取
            </Button>
          )}
        </Space>
      ),
    },
  ];

  const uploadProps: UploadProps = {
    multiple: false,
    beforeUpload: (file) => {
      setFileList([file]);
      return false;
    },
    onRemove: () => setFileList([]),
    fileList: fileList.map((f) => ({ uid: f.name, name: f.name, status: 'done' as const })),
    accept: '.pdf,.md,.html',
  };

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>Ingestion 管理</h2>

      {/* 上传区域 */}
      <Card style={{ marginBottom: 16 }}>
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
        <Dragger {...uploadProps}>
          <p className="ant-upload-drag-icon"><InboxOutlined /></p>
          <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
          <p className="ant-upload-hint">支持 PDF、Markdown、HTML 格式，文件大小不超过 50MB</p>
        </Dragger>
      </Card>

      {/* 摄取记录 */}
      <Card
        title={`摄取记录 (${total})`}
        extra={
          <Button icon={<ReloadOutlined />} onClick={fetchData}>
            刷新
          </Button>
        }
      >
        <Table
          columns={columns}
          dataSource={history}
          rowKey="id"
          loading={loading}
          pagination={{ current: page, pageSize, total, showSizeChanger: true, pageSizeOptions: ['10', '20', '50'], onChange: (p, ps) => { setPage(p); setPageSize(ps); } }}
          locale={{ emptyText: '暂无摄取记录' }}
          size="middle"
        />
      </Card>
    </div>
  );
}
