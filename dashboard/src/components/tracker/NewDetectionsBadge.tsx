import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Bell, X } from 'lucide-react';
import { useDetectionsQuery } from '@/api/detections';

const DISMISS_AFTER_MS = 5 * 60_000;

interface NewDetectionsBadgeProps {
  /** ManualCrawlButton trigger 성공 시각 (ms). null이면 컴포넌트 mount하지 말 것. */
  triggerAt: number;
  onDismiss: () => void;
}

/** 수동 크롤링 후 5분간 새 탐지 알림. UX spec C10 / Pattern 4. */
export function NewDetectionsBadge({ triggerAt, onDismiss }: NewDetectionsBadgeProps) {
  const { data } = useDetectionsQuery({ size: 1, since: 'triggered' });
  const count = data?.totalElements ?? 0;

  useEffect(() => {
    const remaining = Math.max(0, triggerAt + DISMISS_AFTER_MS - Date.now());
    const id = window.setTimeout(onDismiss, remaining);
    return () => window.clearTimeout(id);
  }, [triggerAt, onDismiss]);

  if (count === 0) return null;

  // Link와 dismiss 버튼은 형제로 — HTML5는 interactive content (a > button) nesting 금지.
  return (
    <div
      role="status"
      aria-live="polite"
      className="inline-flex items-center gap-1 rounded-md py-1 pl-2.5 pr-1 text-xs font-medium"
      style={{ background: 'var(--accent)', color: 'var(--on-accent)' }}
    >
      <Link
        to="/detections?since=triggered"
        className="inline-flex items-center gap-1.5 no-underline transition-opacity hover:opacity-90"
        style={{ color: 'inherit' }}
      >
        <Bell className="size-3.5" aria-hidden />
        <span className="tabular-nums">{count}건 새로 들어옴</span>
      </Link>
      <button
        type="button"
        aria-label="알림 닫기"
        onClick={onDismiss}
        className="ml-1 inline-flex size-5 cursor-pointer items-center justify-center rounded bg-transparent transition-opacity hover:opacity-70"
        style={{ color: 'inherit' }}
      >
        <X className="size-3" aria-hidden />
      </button>
    </div>
  );
}
