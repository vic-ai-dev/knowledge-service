/* ============================================================================
 * Knowledge Service — IngestionTraces 摄取追踪页面 (G2)
 * 复刻 Streamlit 布局：可展开卡片列表 + 展开后展示 Pipeline Overview /
 * Stage Timings / Stage Details 标签页
 * ============================================================================ */

import { useState, useEffect, useCallback } from 'react';
import {
  Card, Collapse, Tag, Typography, Spin, Empty, message, Flex,
  Tabs, Descriptions, Progress, Statistic, Row, Col,
} from 'antd';
import { ReloadOutlined, FileTextOutlined } from '@ant-design/icons';
import { getIngestionTraces } from '../api/ingestion';
import type { IngestionTrace } from '../types';

const { Text } = Typography;

const statusConfig: Record<string, { color: string; label: string }> = {
  success: { color: 'green', label: '完成' },
  completed: { color: 'green', label: '完成' },
  failed: { color: 'red', label: '失败' },
  processing: { color: 'blue', label: '处理中' },
  skipped: { color: 'orange', label: '已跳过' },
};

const formatTime = (iso: string | null): string => {
  if (!iso) return '-';
  const d = new Date(iso);
  return d.toISOString().replace('T', ' ').slice(0, 19);
};

const formatDuration = (ms: number | null | undefined): string => {
  if (ms == null) return '—';
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${ms.toFixed(0)}ms`;
};

// ── 展开详情组件 ──────────────────────────────────────────
function TraceDetails({ trace }: { trace: IngestionTrace }) {
  const st = statusConfig[trace.status] || { color: 'default', label: trace.status };
  const stages: Record<string, { duration_ms: number; items: number }> =
    (trace.stages as any) || {};

  return (
    <div style={{ padding: '8px 0 8px 32px' }}>
      {/* 📊 Pipeline Overview */}
      <Text strong style={{ fontSize: 14 }}>📊 Pipeline Overview</Text>
      <div style={{ margin: '8px 0 8px 0' }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          Source: <code>{trace.source_path}</code>
        </Text>
      </div>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}><Statistic title="Chunks" value={trace.total_chunks} suffix="个" /></Col>
        <Col span={6}><Statistic title="Images" value={trace.total_images} suffix="个" /></Col>
        <Col span={6}><Statistic title="Duration" value={formatDuration(trace.total_latency_ms)} /></Col>
        <Col span={6}><Statistic title="Status" valueRender={() => <Tag color={st.color}>{st.label}</Tag>} /></Col>
      </Row>

      {/* ⏱️ Stage Timings */}
      {Object.keys(stages).length > 0 && (
        <>
          <Text strong style={{ fontSize: 14 }}>⏱️ Stage Timings</Text>
          <div style={{ marginTop: 8, marginBottom: 12 }}>
            {Object.entries(stages).map(([name, data]: [string, any]) => {
              const dur = data.duration_ms || 0;
              const maxDur = Math.max(...Object.values(stages).map((s: any) => s.duration_ms || 0), 1);
              const pct = (dur / maxDur) * 100;
              return (
                <div key={name} style={{ marginBottom: 8 }}>
                  <Flex justify="space-between" style={{ marginBottom: 2 }}>
                    <Text style={{ fontSize: 12 }}>{name}</Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>{dur.toFixed(0)}ms</Text>
                  </Flex>
                  <Progress
                    percent={pct}
                    showInfo={false}
                    size="small"
                    strokeColor="#7C3AED"
                    style={{ margin: 0 }}
                  />
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* 🔍 Stage Details Tabs */}
      {Object.keys(stages).length > 0 && (
        <>
          <Text strong style={{ fontSize: 14 }}>🔍 Stage Details</Text>
          <Tabs
            size="small"
            style={{ marginTop: 8 }}
            items={Object.entries(stages).map(([name, data]: [string, any]) => ({
              key: name,
              label: name.charAt(0).toUpperCase() + name.slice(1),
              children: (
                <div style={{ padding: '8px 0' }}>
                  <Descriptions size="small" column={2} bordered>
                    <Descriptions.Item label="Duration">{data.duration_ms?.toFixed(1)}ms</Descriptions.Item>
                    <Descriptions.Item label="Items">{data.items ?? '-'}</Descriptions.Item>
                    {Object.entries(data).filter(([k]) => !['duration_ms', 'items', 'data'].includes(k)).map(([k, v]) => (
                      <Descriptions.Item label={k} key={k} span={2}>
                        {typeof v === 'object' ? JSON.stringify(v) : String(v ?? '-')}
                      </Descriptions.Item>
                    ))}
                  </Descriptions>
                  {data.data && (
                    <pre style={{ fontSize: 11, marginTop: 8, maxHeight: 200, overflow: 'auto' }}>
                      {JSON.stringify(data.data, null, 2)}
                    </pre>
                  )}
                </div>
              ),
            }))}
          />
        </>
      )}

      {/* Error */}
      {trace.error && (
        <div style={{ marginTop: 8 }}>
          <Text type="danger" style={{ fontSize: 12 }}>Error: {trace.error}</Text>
        </div>
      )}
    </div>
  );
}

// ── 主组件 ──────────────────────────────────────────────────
export default function IngestionTraces() {
  const [loading, setLoading] = useState(true);
  const [traces, setTraces] = useState<IngestionTrace[]>([]);
  const [total, setTotal] = useState(0);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const result = await getIngestionTraces({ page: 1, page_size: 100 });
      setTraces(result.items);
      setTotal(result.total);
    } catch (err: any) {
      message.error('加载失败: ' + (err.message || '未知错误'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <div>
      <h2 style={{ marginBottom: 8 }}>🔬 Ingestion 追踪</h2>
      <h3 style={{ marginBottom: 16, fontWeight: 400, color: '#666', fontSize: 15 }}>
        📋 追踪历史 ({total})
      </h3>

      <Card
        styles={{ body: { padding: 0 } }}
        extra={
          <Flex align="center" gap={8}>
            <Spin spinning={loading} size="small" />
            <ReloadOutlined onClick={fetchData} style={{ cursor: 'pointer', color: '#7C3AED' }} />
          </Flex>
        }
      >
        {loading ? (
          <Flex justify="center" style={{ padding: 40 }}>
            <Spin />
          </Flex>
        ) : traces.length === 0 ? (
          <Empty description="暂无追踪记录" image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ padding: 40 }} />
        ) : (
          <Collapse
            ghost
            expandIconPosition="start"
            items={traces.map((trace) => ({
              key: trace.trace_id,
              label: (
                <span>
                  <FileTextOutlined style={{ marginRight: 8, color: '#7C3AED' }} />
                  <Text strong style={{ fontSize: 14 }}>
                    {trace.source_path?.split('/').pop() || '-'}
                  </Text>
                  <Text type="secondary" style={{ marginLeft: 8, fontSize: 13 }}>
                    · {formatDuration(trace.total_latency_ms)} · {formatTime(trace.created_at)}
                  </Text>
                </span>
              ),
              children: <TraceDetails trace={trace} />,
            }))}
          />
        )}

        {total > 0 && !loading && (
          <div style={{ padding: '12px 16px', borderTop: '1px solid #f0f0f0', textAlign: 'center' }}>
            <Text type="secondary" style={{ fontSize: 12 }}>显示 {traces.length} 条记录</Text>
          </div>
        )}
      </Card>
    </div>
  );
}
