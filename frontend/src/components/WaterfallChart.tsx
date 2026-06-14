/* ============================================================================
 * Knowledge Service — WaterfallChart 瀑布图组件 (G4)
 * 用于 Ingestion 摄取阶段时序可视化
 * ============================================================================ */

import { Card } from 'antd';
import type { ReactNode } from 'react';

interface Stage {
  name: string;
  start_ms: number;
  duration_ms: number;
  color?: string;
}

interface WaterfallChartProps {
  title: string;
  stages: Stage[];
  totalDuration: number;
  loading?: boolean;
  extra?: ReactNode;
}

const STAGE_COLORS: Record<string, string> = {
  Load: '#7C3AED',
  Split: '#A78BFA',
  Encode: '#F97316',
  Index: '#10B981',
  'BM25 Index': '#3B82F6',
  Transform: '#F59E0B',
  ChunkRefine: '#EF4444',
  Metadata: '#8B5CF6',
  VectorUpsert: '#06B6D4',
  Cleanup: '#6B7280',
};

export default function WaterfallChart({
  title, stages, totalDuration, loading = false, extra,
}: WaterfallChartProps) {
  if (loading) {
    return <Card title={title} loading />;
  }

  if (stages.length === 0) {
    return (
      <Card title={title} extra={extra}>
        <div style={{ padding: 32, textAlign: 'center', color: '#999' }}>
          暂无阶段数据
        </div>
      </Card>
    );
  }

  const barHeight = 28;
  const gap = 8;
  const stagesHeight = stages.length * (barHeight + gap);
  const chartHeight = stagesHeight + 60;
  const paddingLeft = 140;
  const paddingRight = 80;
  const plotWidth = 400;
  const totalW = paddingLeft + plotWidth + paddingRight;

  return (
    <Card title={title} extra={extra}>
      <div style={{ position: 'relative', width: '100%', overflowX: 'auto' }}>
        <svg
          width="100%"
          height={chartHeight}
          style={{ display: 'block', minWidth: totalW }}
          viewBox={`0 0 ${totalW} ${chartHeight}`}
          preserveAspectRatio="xMidYMid meet"
        >
          {/* 时间刻度线 */}
          {Array.from({ length: 6 }).map((_, i) => {
            const x = paddingLeft + (i / 5) * plotWidth;
            return (
              <g key={i}>
                <line
                  x1={x} y1={0} x2={x} y2={stagesHeight}
                  stroke="#f0f0f0" strokeWidth={1}
                />
                <text
                  x={x} y={stagesHeight + 16}
                  textAnchor="middle" fontSize={11} fill="#999"
                >
                  {Math.round((i / 5) * totalDuration)}ms
                </text>
              </g>
            );
          })}

          {/* 阶段条 */}
          {stages.map((stage, i) => {
            const y = i * (barHeight + gap) + 4;
            const xStart = paddingLeft + (stage.start_ms / Math.max(totalDuration, 1)) * plotWidth;
            const barWidth = Math.max(4, (stage.duration_ms / Math.max(totalDuration, 1)) * plotWidth);
            const barColor = stage.color || STAGE_COLORS[stage.name] || '#7C3AED';

            return (
              <g key={stage.name}>
                {/* 阶段名称 */}
                <text
                  x={paddingLeft - 8}
                  y={y + barHeight / 2 + 4}
                  textAnchor="end"
                  fontSize={12}
                  fill="#333"
                >
                  {stage.name}
                </text>

                {/* 进度条 */}
                <rect
                  x={xStart}
                  y={y}
                  width={barWidth}
                  height={barHeight}
                  rx={4}
                  fill={barColor}
                  opacity={0.85}
                />

                {/* 耗时标注 */}
                <text
                  x={xStart + barWidth + 6}
                  y={y + barHeight / 2 + 4}
                  fontSize={11}
                  fill="#666"
                >
                  {stage.duration_ms}ms
                </text>
              </g>
            );
          })}

          {/* 总耗时标注 */}
          <text
            x={paddingLeft + plotWidth}
            y={stagesHeight + 16}
            textAnchor="end"
            fontSize={11}
            fill="#333"
            fontWeight={600}
          >
            总计: {totalDuration}ms
          </text>
        </svg>
      </div>
    </Card>
  );
}

export type { Stage, WaterfallChartProps };
