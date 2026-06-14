/* ============================================================================
 * Knowledge Service — HistoryChart 趋势折线图 (A9)
 * ============================================================================ */

import { Card } from 'antd';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

interface DataPoint {
  label: string;
  value: number;
}

interface HistoryChartProps {
  title: string;
  data: DataPoint[];
  dataKey?: string;
  loading?: boolean;
  height?: number;
  color?: string;
}

export default function HistoryChart({
  title, data, dataKey = 'value', loading = false, height = 300, color = '#7C3AED',
}: HistoryChartProps) {
  return (
    <Card title={title} loading={loading}>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip />
          <Line
            type="monotone"
            dataKey={dataKey}
            stroke={color}
            strokeWidth={2}
            dot={{ r: 3 }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
}
