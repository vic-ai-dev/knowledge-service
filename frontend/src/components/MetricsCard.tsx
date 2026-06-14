/* ============================================================================
 * Knowledge Service — MetricsCard 通用指标卡片 (A9)
 * ============================================================================ */

import { Card, Statistic } from 'antd';
import type { ReactNode } from 'react';

interface MetricsCardProps {
  title: string;
  value: number | string;
  precision?: number;
  suffix?: string;
  prefix?: ReactNode;
  loading?: boolean;
}

export default function MetricsCard({
  title, value, precision, suffix, prefix, loading = false,
}: MetricsCardProps) {
  return (
    <Card hoverable loading={loading}>
      <Statistic
        title={title}
        value={value}
        precision={precision}
        suffix={suffix}
        prefix={prefix}
      />
    </Card>
  );
}
