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
import type { DotItemDotProps } from 'recharts/types/util/types';

type LineDatum = { name: string; value: number; date?: string };

interface LineChartProps {
  data: LineDatum[];
  onSelect?: (entry: LineDatum) => void;
}

export function LineChart({ data, onSelect }: LineChartProps) {
  const isMobile = useIsMobile();
  const color = 'var(--primary)';
  const interactive = Boolean(onSelect);

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
          dot={(props) => (
            <SelectableDot
              {...props}
              radius={isMobile ? 3.5 : 4}
              color={color}
              interactive={interactive}
            />
          )}
          activeDot={{ r: isMobile ? 4 : 5 }}
        />
      </RechartsLineChart>
    </ResponsiveContainer>
  );
}

function SelectableDot({
  cx,
  cy,
  payload,
  radius,
  color,
  interactive,
}: DotItemDotProps & {
  radius: number;
  color: string;
  interactive: boolean;
}) {
  const entry = payload as LineDatum | undefined;
  if (typeof cx !== 'number' || typeof cy !== 'number') return null;
  const ariaLabel = entry?.date ? `${entry.date} 탐지 목록 보기` : undefined;
  const targetSize = Math.max(radius * 4, 18);

  if (interactive && entry) {
    const href = entry.date ? `/detections?date=${entry.date}` : '/detections';
    return (
      <foreignObject
        x={cx - targetSize / 2}
        y={cy - targetSize / 2}
        width={targetSize}
        height={targetSize}
      >
        <a
          href={href}
          aria-label={ariaLabel}
          style={{
            alignItems: 'center',
            background: 'transparent',
            border: 0,
            cursor: 'pointer',
            display: 'flex',
            height: '100%',
            justifyContent: 'center',
            padding: 0,
            width: '100%',
          }}
        >
          <span
            aria-hidden
            style={{
              background: color,
              border: '2px solid var(--background)',
              borderRadius: '999px',
              display: 'block',
              height: radius * 2,
              width: radius * 2,
            }}
          />
        </a>
      </foreignObject>
    );
  }

  return (
    <circle
      cx={cx}
      cy={cy}
      r={radius}
      fill={color}
      stroke="var(--background)"
      strokeWidth={2}
    />
  );
}
