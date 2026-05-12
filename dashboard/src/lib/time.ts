import { formatDistanceToNow } from 'date-fns';
import { ko } from 'date-fns/locale';

/** ISO 시각 / Date / ms timestamp → "N분 전" 한국어 표기. 파싱 실패 시 "—" fallback. */
export function formatRelativeTime(input: string | number | Date): string {
  const t = typeof input === 'string' ? Date.parse(input) : input instanceof Date ? input.getTime() : input;
  if (!Number.isFinite(t)) return '—';
  return formatDistanceToNow(new Date(t), { addSuffix: true, locale: ko });
}
