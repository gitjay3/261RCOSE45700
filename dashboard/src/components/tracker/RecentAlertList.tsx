import { useNavigate, Link } from 'react-router-dom';
import { formatDistanceToNow } from 'date-fns';
import { ko } from 'date-fns/locale';
import { AlertTriangle, AlertCircle, Circle } from 'lucide-react';
import { useDetectionsQuery } from '@/api/detections';
import { TypeIcon } from './TypeIcon';
import { getTypeLabel } from './labels';
import { cn } from '@/lib/utils';
import type { Detection } from '@/types/api';

const RECENT_LIMIT = 5;

/**
 * Recent · High confidence — Dashboard Hero 아래 노출되는 최신 탐지 5건.
 * mockup의 alert-row + sev-v14 (N1) 패턴.
 */
export function RecentAlertList() {
  const navigate = useNavigate();
  const { data, isLoading } = useDetectionsQuery({ size: RECENT_LIMIT });

  const items = data?.content?.slice(0, RECENT_LIMIT) ?? [];
  const total = data?.totalElements ?? 0;

  return (
    <section style={{ marginBottom: 'var(--pad-section)' }}>
      <div className="mb-4 flex items-baseline justify-between">
        <span
          className="text-xs font-semibold uppercase"
          style={{ color: 'var(--fg-3)', letterSpacing: 'var(--tracking-wider)' }}
        >
          Recent · High confidence
        </span>
        <Link
          to="/detections"
          className="text-xs no-underline hover:underline"
          style={{ color: 'var(--accent)' }}
        >
          전체 {total}건 →
        </Link>
      </div>

      <div
        className="overflow-hidden rounded-md border"
        style={{
          background: 'var(--bg-elev)',
          borderColor: 'var(--border-1)',
        }}
      >
        {isLoading ? (
          <div
            className="px-6 py-8 text-center text-sm"
            style={{ color: 'var(--fg-3)' }}
          >
            불러오는 중…
          </div>
        ) : items.length === 0 ? (
          <div
            className="px-6 py-8 text-center text-sm"
            style={{ color: 'var(--fg-3)' }}
          >
            아직 탐지된 항목이 없습니다
          </div>
        ) : (
          items.map((d) => (
            <AlertRow
              key={d.id}
              detection={d}
              onClick={() => navigate(`/detections/${d.id}`)}
            />
          ))
        )}
      </div>
    </section>
  );
}

function AlertRow({ detection, onClick }: { detection: Detection; onClick: () => void }) {
  const severity =
    detection.confidence >= 0.8 ? 'high' : detection.confidence >= 0.5 ? 'medium' : 'low';
  const time = formatDistanceToNow(new Date(detection.detectedAt), {
    addSuffix: true,
    locale: ko,
  });

  return (
    <button
      type="button"
      onClick={onClick}
      data-severity={severity}
      className={cn(
        'group grid w-full cursor-pointer items-center border-t bg-transparent text-left transition-colors first:border-t-0 hover:bg-[--hover]',
        // 좌측 6px 색 막대 (box-shadow inset) + 약한 tint — Carbon borderStart 패턴
        'data-[severity=high]:shadow-[inset_6px_0_0_var(--crit-bg)] data-[severity=high]:bg-[oklch(0.52_0.21_25/0.06)]',
        'data-[severity=medium]:shadow-[inset_6px_0_0_var(--warn-bg)] data-[severity=medium]:bg-[oklch(0.55_0.16_55/0.05)]',
      )}
      style={{
        gridTemplateColumns: '52px 28px minmax(120px, 180px) minmax(0, 1fr) 90px',
        gap: 'clamp(10px, 1vw, 18px)',
        padding: 'var(--pad-alert-row-y) var(--pad-alert-row-x)',
        borderColor: 'var(--border-1)',
      }}
    >
      <SeverityBadge confidence={detection.confidence} />
      <TypeIcon type={detection.type} showLabel={false} />
      <div className="flex min-w-0 flex-col gap-0.5">
        <span
          className="font-medium"
          style={{ fontSize: 'var(--size-alert-type)', color: 'var(--fg)' }}
        >
          {getTypeLabel(detection.type)}
        </span>
        <span
          className="font-mono text-xs"
          style={{ color: 'var(--fg-3)', fontFeatureSettings: "'liga' off" }}
        >
          {detection.siteName}
        </span>
      </div>
      <span
        className="overflow-hidden text-ellipsis whitespace-nowrap"
        style={{
          fontSize: 'var(--size-alert-snippet)',
          color: 'var(--fg-2)',
        }}
      >
        {detection.translatedText ?? detection.rawText}
      </span>
      <span
        className="font-mono text-right text-xs tabular-nums"
        style={{ color: 'var(--fg-3)' }}
      >
        {time}
      </span>
    </button>
  );
}

function SeverityBadge({ confidence }: { confidence: number }) {
  const level: 'high' | 'medium' | 'low' =
    confidence >= 0.8 ? 'high' : confidence >= 0.5 ? 'medium' : 'low';
  const Icon = level === 'high' ? AlertTriangle : level === 'medium' ? AlertCircle : Circle;
  const numText = confidence.toFixed(2).replace(/^0/, '');

  const chipClass =
    level === 'high'
      ? 'bg-confidence-high-bg text-white'
      : level === 'medium'
        ? 'bg-confidence-medium-bg text-white'
        : 'border';

  const lowStyle: React.CSSProperties =
    level === 'low'
      ? { borderColor: 'var(--border-1)', color: 'var(--fg-3)' }
      : {};

  return (
    <span
      className={cn(
        'inline-flex size-11 flex-col items-center justify-center gap-[3px] rounded-md font-mono leading-none',
        chipClass,
      )}
      style={lowStyle}
    >
      <Icon
        aria-hidden
        className={level === 'low' ? 'size-2.5' : 'size-[13px]'}
        strokeWidth={2.5}
      />
      <span className="text-[13px] font-bold tabular-nums tracking-tight">
        {numText}
      </span>
    </span>
  );
}
