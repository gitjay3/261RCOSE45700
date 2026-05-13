import {
  CartesianGrid,
  Line,
  LineChart as RechartsLineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { chartTooltipProps } from './tooltip';
import { useIsMobile } from '@/lib/useIsMobile';

interface LineChartProps {
  data: Array<{ name: string; value: number }>;
}

export function LineChart({ data }: LineChartProps) {
  const isMobile = useIsMobile();
  const color = 'var(--primary)';

  return (
    <ResponsiveContainer width="100%" height={isMobile ? 200 : 260}>
      <RechartsLineChart
        data={data}
        margin={{
          top: isMobile ? 12 : 16,
          right: isMobile ? 12 : 16,
          bottom: isMobile ? 8 : 16,
          left: 0,
        }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis
          dataKey="name"
          stroke="var(--muted-foreground)"
          fontSize={isMobile ? 10 : 12}
          // 모바일 좁은 폭에서 라벨 겹침 방지 — 시작/끝 보장 + 자동 thinning.
          interval="preserveStartEnd"
          minTickGap={isMobile ? 16 : 5}
        />
        <YAxis
          allowDecimals={false}
          stroke="var(--muted-foreground)"
          fontSize={isMobile ? 10 : 12}
          width={isMobile ? 28 : 40}
        />
        <Tooltip {...chartTooltipProps} />
        <Line
          type="monotone"
          dataKey="value"
          stroke={color}
          strokeWidth={2}
          dot={{ r: isMobile ? 2.5 : 3, fill: color }}
          activeDot={{ r: isMobile ? 4 : 5 }}
        />
      </RechartsLineChart>
    </ResponsiveContainer>
  );
}
