/* ============================================================================
 * Knowledge Service — Overview 系统总览页面 (G1)
 * ============================================================================ */

import { useState, useEffect } from 'react';
import { Card, Row, Col, Statistic, Table, Spin, Alert, Tag, Descriptions } from 'antd';
import {
  FileTextOutlined,
  DatabaseOutlined,
  CloudUploadOutlined,
  CheckCircleOutlined,
  BookOutlined,
  TranslationOutlined,
  ApartmentOutlined,
  RobotOutlined,
  ExperimentOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import type { SystemStats } from '../types';

const MOCK_STATS: SystemStats = {
  total_documents: 128,
  total_chunks: 4823,
  total_collections: 4,
  by_category: {
    employee_handbook: 42,
    compliance: 35,
    technical_spec: 31,
    architecture: 20,
  },
  by_language: {
    zh: 89,
    en: 39,
  },
};

const categoryLabels: Record<string, string> = {
  employee_handbook: '员工手册',
  compliance: '合规指南',
  technical_spec: '技术规范',
  architecture: '架构文档',
};

const categoryColors: Record<string, string> = {
  employee_handbook: '#7C3AED',
  compliance: '#3B82F6',
  technical_spec: '#F97316',
  architecture: '#10B981',
};

const langLabels: Record<string, string> = {
  zh: '中文',
  en: 'English',
};

const configItems = [
  { icon: <RobotOutlined />, label: 'LLM', value: 'OpenAI-compatible (deepseek-v4-flash)' },
  { icon: <ExperimentOutlined />, label: 'Embedding', value: 'Ollama (qwen3-embedding:0.6b, 1536d)' },
  { icon: <DatabaseOutlined />, label: 'VectorStore', value: 'pgvector (PostgreSQL + HNSW)' },
  { icon: <ThunderboltOutlined />, label: 'Reranker', value: 'Ollama (Qwen3-Reranker-0.6B) [已启用]' },
  { icon: <ApartmentOutlined />, label: 'Sparse Backend', value: 'pg_bm25' },
];

export default function Overview() {
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // 模拟 API 调用
    const timer = setTimeout(() => {
      setStats(MOCK_STATS);
      setLoading(false);
    }, 600);
    return () => clearTimeout(timer);
  }, []);

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
        <Spin size="large" tip="加载统计数据..." />
      </div>
    );
  }

  if (error) {
    return <Alert type="error" message="加载失败" description={error} showIcon />;
  }

  const categoryData = Object.entries(stats!.by_category).map(([key, value]) => ({
    key,
    category: categoryLabels[key] || key,
    count: value,
    color: categoryColors[key] || '#999',
  }));

  const langData = Object.entries(stats!.by_language).map(([key, value]) => ({
    key,
    language: langLabels[key] || key,
    count: value,
  }));

  return (
    <div>
      <h2 style={{ marginBottom: 24 }}>系统总览</h2>

      {/* 核心指标 */}
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable>
            <Statistic
              title="文档总数"
              value={stats!.total_documents}
              prefix={<FileTextOutlined style={{ color: '#7C3AED' }} />}
              valueStyle={{ color: '#4C1D95' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable>
            <Statistic
              title="Chunk 总数"
              value={stats!.total_chunks}
              prefix={<DatabaseOutlined style={{ color: '#3B82F6' }} />}
              valueStyle={{ color: '#1E40AF' }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable>
            <Statistic
              title="知识库"
              value={stats!.total_collections}
              prefix={<BookOutlined style={{ color: '#F97316' }} />}
              valueStyle={{ color: '#C2410C' }}
              suffix="个"
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable>
            <Statistic
              title="健康状态"
              value="运行中"
              prefix={<CheckCircleOutlined style={{ color: '#52c41a' }} />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
      </Row>

      {/* 第二行：分布统计 */}
      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        <Col xs={24} lg={12}>
          <Card title="文档分类分布">
            <Table
              dataSource={categoryData}
              columns={[
                {
                  title: '分类', dataIndex: 'category', key: 'category',
                  render: (text: string, record: typeof categoryData[0]) => (
                    <span>
                      <span style={{
                        display: 'inline-block', width: 10, height: 10, borderRadius: '50%',
                        backgroundColor: record.color, marginRight: 8,
                      }} />
                      {text}
                    </span>
                  ),
                },
                {
                  title: '文档数', dataIndex: 'count', key: 'count',
                  render: (val: number) => <Tag color="purple">{val}</Tag>,
                },
                {
                  title: '占比', key: 'ratio',
                  render: (_: unknown, record: typeof categoryData[0]) => {
                    const pct = ((record.count / stats!.total_documents) * 100).toFixed(1);
                    return `${pct}%`;
                  },
                },
              ]}
              pagination={false}
              size="small"
            />
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="语言分布">
            <Table
              dataSource={langData}
              columns={[
                { title: '语言', dataIndex: 'language', key: 'language' },
                {
                  title: '文档数', dataIndex: 'count', key: 'count',
                  render: (val: number) => <Tag color="blue">{val}</Tag>,
                },
                {
                  title: '占比', key: 'ratio',
                  render: (_: unknown, record: typeof langData[0]) => {
                    const pct = ((record.count / stats!.total_documents) * 100).toFixed(1);
                    return `${pct}%`;
                  },
                },
              ]}
              pagination={false}
              size="small"
            />
          </Card>
        </Col>
      </Row>

      {/* 组件配置 */}
      <Card title="组件配置" style={{ marginTop: 24 }}>
        <Row gutter={[16, 16]}>
          {configItems.map((item) => (
            <Col xs={24} sm={12} lg={8} key={item.label}>
              <Descriptions size="small" column={1} style={{ padding: '8px 0' }}>
                <Descriptions.Item
                  label={<span>{item.icon} <strong>{item.label}</strong></span>}
                  labelStyle={{ minWidth: 90 }}
                >
                  <code style={{ fontSize: 12, color: '#555' }}>{item.value}</code>
                </Descriptions.Item>
              </Descriptions>
            </Col>
          ))}
        </Row>
      </Card>
    </div>
  );
}
