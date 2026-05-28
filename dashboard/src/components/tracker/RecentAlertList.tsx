import { useNavigate, Link } from 'react-router-dom';
import { useDetectionsSuspenseQuery } from '@/api/detections';
import { ConfidenceBadge } from './ConfidenceBadge';
import { TypeIcon } from './TypeIcon';
import { getTypeLabel } from './labels';
import { SEVERITY_TINT_CLASSES, severityOfDetection } from '@/lib/severity';
import { formatRelativeTime } from '@/lib/time';
import { cn } from '@/lib/utils';
import type { Detection } from '@/types/api';

const RECENT_LIMIT = 5;

export function RecentAlertList() {
  const navigate = useNavigate();
  const { data } = useDetectionsSuspenseQuery({ size: RECENT_LIMIT * 3 });
  const items = data.content.filter((d) => d.isIllegal).slice(0, RECENT_LIMIT);
  const total = data.totalElements;

  return (
    <section style={{ marginBottom: 'var(--pad-section)' }}>
      <div className="mb-4 flex items-baseline justify-between">
        <span
          className="text-fg-3 text-xs font-semibold uppercase"
          style={{ letterSpacing: 'var(--tracking-wider)' }}
        >
          최근 탐지
        </span>
        <Link
          to="/detections"
          className="text-accent text-xs no-underline hover:underline"
        >
          전체 {total}건 →
        </Link>
      </div>

      <div
        role="list"
        className="bg-bg-elev border-border-1 overflow-hidden rounded-md border"
      >
        {items.length === 0 ? (
          <div className="text-fg-3 px-6 py-8 text-center text-sm">
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
  const severity = severityOfDetection(detection);
  const time = formatRelativeTime(detection.detectedAt);
  const snippet = detection.translatedText ?? detection.rawText;

  return (
    <button
      type="button"
      role="listitem"
      onClick={onClick}
      data-severity={severity}
      title={snippet}
      className={cn(
        'group border-border-1 block w-full cursor-pointer border-t bg-transparent text-left transition-colors first:border-t-0 hover:bg-[var(--hover)]',
        SEVERITY_TINT_CLASSES,
      )}
    >
      {/* Mobile (< md) */}
      <div className="flex flex-col gap-1.5 px-4 py-3 md:hidden">
        <div className="flex items-center gap-2.5">
          <ConfidenceBadge score={detection.confidence} tier={detection.tier} isIllegal={detection.isIllegal} aria-hidden />
          <TypeIcon type={detection.type} />
          <span
            className="text-fg-3 font-mono ml-auto text-xs tabular-nums"
            style={{ fontFeatureSettings: "'liga' off" }}
          >
            {time}
          </span>
        </div>
        <span
          className="text-fg-3 font-mono text-xs"
          style={{ fontFeatureSettings: "'liga' off" }}
        >
          {detection.siteName}
        </span>
        <p
          className="text-fg-2 line-clamp-2 text-sm leading-relaxed"
          style={{ fontSize: 'var(--size-alert-snippet)' }}
        >
          {snippet}
        </p>
      </div>

      {/* Desktop (≥ md) */}
      <div
        className="hidden items-center md:grid"
        style={{
          gridTemplateColumns: '52px 28px minmax(120px, 180px) minmax(0, 1fr) 90px',
          gap: 'clamp(10px, 1vw, 18px)',
          padding: 'var(--pad-alert-row-y) var(--pad-alert-row-x)',
        }}
      >
        <ConfidenceBadge score={detection.confidence} tier={detection.tier} isIllegal={detection.isIllegal} aria-hidden />
        <TypeIcon type={detection.type} showLabel={false} />
        <div className="flex min-w-0 flex-col gap-0.5">
          <span
            className="text-fg font-medium"
            style={{ fontSize: 'var(--size-alert-type)' }}
          >
            {getTypeLabel(detection.type)}
          </span>
          <span
            className="text-fg-3 font-mono text-xs"
            style={{ fontFeatureSettings: "'liga' off" }}
          >
            {detection.siteName}
          </span>
        </div>
        <span
          className="text-fg-2 overflow-hidden text-ellipsis whitespace-nowrap"
          style={{ fontSize: 'var(--size-alert-snippet)' }}
        >
          {snippet}
        </span>
        <span className="text-fg-3 font-mono text-right text-xs tabular-nums">
          {time}
        </span>
      </div>
    </button>
  );
}
