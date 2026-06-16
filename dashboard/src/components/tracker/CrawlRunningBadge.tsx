import { useCrawlJobStatusQuery, useCrawlRunningQuery } from '@/api/detections';

const LABEL: Record<'manual' | 'schedule' | 'unknown', string> = {
  manual: '수동 크롤링 진행 중',
  schedule: '자동 크롤링 진행 중',
  unknown: '크롤링 진행 중',
};

export function CrawlRunningBadge() {
  const { data, isLoading } = useCrawlRunningQuery();
  const isSchedule = data?.running && data.trigger === 'schedule';
  // 자동(스케줄) run만 진행률 표시 — 수동은 ManualCrawlButton 다이얼로그가 이미 보여줌.
  const { data: scheduleJob } = useCrawlJobStatusQuery(isSchedule ? 'schedule' : null);

  if (isLoading || !data) return null;

  const running = data.running;
  const label = running ? LABEL[data.trigger ?? 'unknown'] : '크롤링 대기 중';
  const progress = isSchedule && scheduleJob
    ? `${scheduleJob.currentSite || '준비 중'} · ${scheduleJob.percent}%`
    : null;
  const dotColor = running ? 'var(--accent)' : 'var(--fg-3)';

  return (
    <span
      role="status"
      aria-label={progress ? `${label} — ${progress}` : label}
      className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium"
      style={{ borderColor: 'var(--border-1)', background: 'var(--bg-elev)', color: 'var(--fg-2)' }}
    >
      <span className="relative flex size-2">
        {running && (
          <span
            className="motion-safe:absolute motion-safe:inline-flex motion-safe:size-full motion-safe:animate-ping motion-safe:rounded-full motion-safe:opacity-75"
            style={{ background: dotColor }}
            aria-hidden
          />
        )}
        <span
          className="relative inline-flex size-2 rounded-full"
          style={{ background: dotColor }}
          aria-hidden
        />
      </span>
      {label}
      {progress && <span style={{ color: 'var(--fg-3)' }} className="font-mono">{progress}</span>}
    </span>
  );
}
