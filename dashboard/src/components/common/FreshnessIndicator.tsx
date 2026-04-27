import { useEffect, useState } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { ko } from 'date-fns/locale';
import { AlertCircle, Loader2 } from 'lucide-react';

interface FreshnessIndicatorProps {
  /** TanStack Query dataUpdatedAt (epoch ms). undefined means data not yet fetched. */
  lastUpdatedAt: number | undefined;
  isFetching: boolean;
  /** Threshold for "stale" state in milliseconds. Default 5 minutes. */
  staleThresholdMs?: number;
}

const DEFAULT_STALE_THRESHOLD_MS = 5 * 60 * 1000;
const RELATIVE_LABEL_TICK_MS = 30_000;

export function FreshnessIndicator({
  lastUpdatedAt,
  isFetching,
  staleThresholdMs = DEFAULT_STALE_THRESHOLD_MS,
}: FreshnessIndicatorProps) {
  // 30초마다 현재 시각을 다시 읽어 "N분 전" 라벨과 stale 판정을 갱신한다.
  // Date.now()를 render 중 직접 호출하면 react-hooks/purity 위반이라 state로 관리.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), RELATIVE_LABEL_TICK_MS);
    return () => clearInterval(id);
  }, []);

  if (isFetching) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="inline-flex items-center gap-2 text-xs text-muted-foreground"
      >
        <Loader2 className="size-3 animate-spin" aria-hidden />
        <span>갱신 중...</span>
      </div>
    );
  }

  if (!lastUpdatedAt) return null;

  const elapsed = now - lastUpdatedAt;
  const isStale = elapsed > staleThresholdMs;

  if (isStale) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="inline-flex items-center gap-2 text-xs text-destructive"
      >
        <AlertCircle className="size-3" aria-hidden />
        <span>데이터 갱신 지연됨</span>
      </div>
    );
  }

  const label = formatDistanceToNow(new Date(lastUpdatedAt), {
    addSuffix: true,
    locale: ko,
  });

  return (
    <div
      role="status"
      aria-live="polite"
      className="inline-flex items-center gap-2 text-xs text-muted-foreground"
    >
      <span className="relative inline-flex size-2" aria-hidden>
        <span className="bg-success absolute inline-flex h-full w-full animate-ping rounded-full opacity-50" />
        <span className="bg-success relative inline-flex size-2 rounded-full" />
      </span>
      <span>{label} 업데이트</span>
    </div>
  );
}
