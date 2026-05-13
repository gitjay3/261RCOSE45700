import {
  Cell,
  Legend,
  Pie,
  PieChart as RechartsPieChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import { CHART_PALETTE_VARS } from './colors';
import { chartTooltipProps } from './tooltip';
import { useIsMobile } from '@/lib/useIsMobile';

interface PieChartProps {
  data: Array<{ name: string; value: number }>;
  /** Optional override for slice colors. Defaults to CHART_PALETTE_VARS. */
  colors?: readonly string[];
}

/**
 * 모바일(< md)에서 우측 legend는 좁은 폭에 파이를 짓누르므로 하단 가로 legend로 전환.
 */
export function PieChart({ data, colors = CHART_PALETTE_VARS }: PieChartProps) {
  const isMobile = useIsMobile();

  return (
    <ResponsiveContainer width="100%" height={isMobile ? 220 : 260}>
      <RechartsPieChart>
        <Pie
          data={data}
          dataKey="value"
          nameKey="name"
          cx={isMobile ? '50%' : '40%'}
          cy={isMobile ? '42%' : '50%'}
          innerRadius={isMobile ? 38 : 50}
          outerRadius={isMobile ? 70 : 90}
          paddingAngle={data.length > 1 ? 1 : 0}
          stroke="var(--background)"
          strokeWidth={2}
        >
          {data.map((entry, idx) => (
            <Cell key={entry.name} fill={colors[idx % colors.length]} />
          ))}
        </Pie>
        <Tooltip {...chartTooltipProps} />
        <Legend
          layout={isMobile ? 'horizontal' : 'vertical'}
          verticalAlign={isMobile ? 'bottom' : 'middle'}
          align={isMobile ? 'center' : 'right'}
          iconType="square"
          wrapperStyle={{
            fontSize: isMobile ? 11 : 12,
            paddingLeft: isMobile ? 0 : 16,
            paddingTop: isMobile ? 8 : 0,
          }}
        />
      </RechartsPieChart>
    </ResponsiveContainer>
  );
}
