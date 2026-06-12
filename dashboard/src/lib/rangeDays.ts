import type { DetectionDateRange } from '@/types/api';

export const MIN_RANGE_DAYS = 1;
export const MAX_RANGE_DAYS = 365;

export function clampRangeDays(days: number): number {
  if (!Number.isFinite(days)) return 7;
  return Math.min(MAX_RANGE_DAYS, Math.max(MIN_RANGE_DAYS, Math.round(days)));
}

export function daysToRange(days: number): DetectionDateRange {
  return `${clampRangeDays(days)}d`;
}

export function rangeToDays(range: string | undefined, fallback = 7): number {
  if (!range) return fallback;
  const raw = range.trim().toLowerCase().endsWith('d')
    ? range.trim().slice(0, -1)
    : range.trim();
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? clampRangeDays(parsed) : fallback;
}
