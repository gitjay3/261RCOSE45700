import {
  Bar,
  BarChart as RechartsBarChart,
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { chartTooltipProps } from './tooltip';
import { useIsMobile } from '@/lib/useIsMobile';

interface BarChartProps {
  data: Array<{ name: string; value: number }>;
}

/**
 * 모바일에선 YAxis 폭/라벨 길이를 축소해 좁은 화면에서 카테고리 라벨이 차트 영역을
 * 침범하지 않게 한다.
 */
export function BarChart({ data }: BarChartProps) {
  const isMobile = useIsMobile();
  const yAxisWidth = isMobile ? 84 : 140;
  const truncateAt = isMobile ? 10 : 18;
  const truncateLabel = (name: string) =>
    name.length > truncateAt ? name.slice(0, truncateAt - 1) + '…' : name;

  return (
    <ResponsiveContainer width="100%" height={isMobile ? 200 : 260}>
      <RechartsBarChart
        data={data}
        layout="vertical"
        margin={{ top: 8, right: isMobile ? 24 : 32, bottom: 8, left: 8 }}
      >
        <CartesianGrid horizontal={false} stroke="var(--border)" strokeDasharray="3 3" />
        <XAxis
          type="number"
          stroke="var(--muted-foreground)"
          fontSize={isMobile ? 10 : 11}
          allowDecimals={false}
        />
        <YAxis
          dataKey="name"
          type="category"
          stroke="var(--muted-foreground)"
          fontSize={isMobile ? 10 : 12}
          width={yAxisWidth}
          tickLine={false}
          axisLine={false}
          tickFormatter={truncateLabel}
        />
        <Tooltip {...chartTooltipProps} />
        <Bar
          dataKey="value"
          fill="var(--foreground)"
          fillOpacity={0.85}
          radius={[0, 4, 4, 0]}
          barSize={isMobile ? 12 : 14}
        >
          <LabelList
            dataKey="value"
            position="right"
            fill="var(--foreground)"
            fontSize={isMobile ? 10 : 12}
            fontFamily="var(--font-mono)"
          />
        </Bar>
      </RechartsBarChart>
    </ResponsiveContainer>
  );
}
