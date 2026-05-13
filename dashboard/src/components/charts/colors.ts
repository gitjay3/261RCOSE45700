import type { DetectionType } from '@/types/api';

/**
 * Tracker chart palette (UX Spec Step 8) — 식별 전용 색.
 * 의미적 위계 없이 채도/명도가 비슷하게 설계. 위험 시그널은 confidence 색이 담당.
 */
const TYPE_TO_CHART_VAR: Record<DetectionType, string> = {
  매크로_판매: '--chart-1',
  핵_배포: '--chart-2',
  계정_거래: '--chart-3',
  리세마라: '--chart-4',
  기타: '--chart-5',
};

export function colorForType(type: DetectionType): string {
  return `var(${TYPE_TO_CHART_VAR[type]})`;
}

export const CHART_PALETTE_VARS = [
  'var(--chart-1)',
  'var(--chart-2)',
  'var(--chart-3)',
  'var(--chart-4)',
  'var(--chart-5)',
] as const;
