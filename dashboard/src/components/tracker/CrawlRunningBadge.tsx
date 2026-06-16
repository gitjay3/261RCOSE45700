import { useCrawlJobStatusQuery, useCrawlRunningQuery } from '@/api/detections';

const LABEL: Record<'manual' | 'schedule' | 'unknown', string> = {
  manual: '수동 크롤링 진행 중',
  schedule: '자동 크롤링 진행 중',
  unknown: '크롤링 진행 중',
};

export function CrawlRunningBadge() {
  const { data } = useCrawlRunningQuery();
  const isSchedule = data?.running && data.trigger === 'schedule';
  // 자동(스케줄) run만 진행률 표시 — 수동은 ManualCrawlButton 다이얼로그가 이미 보여줌.
  const { data: scheduleJob } = useCrawlJobStatusQuery(isSchedule ? 'schedule' : null);

  if (!data?.running) return null;
  const label = LABEL[data.trigger ?? 'unknown'];
  const progress = isSchedule && scheduleJob
    ? `${scheduleJob.currentSite || '준비 중'} · ${scheduleJob.percent}%`
    : null;

  return (
    <span
      role="status"
      aria-label={progress ? `${label} — ${progress}` : label}
      className="inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium"
      style={{ borderColor: 'var(--border-1)', background: 'var(--bg-elev)', color: 'var(--fg-2)' }}
    >
      <span className="relative flex size-2">
        <span
          className="motion-safe:absolute motion-safe:inline-flex motion-safe:size-full motion-safe:animate-ping motion-safe:rounded-full motion-safe:opacity-75"
          style={{ background: 'var(--accent)' }}
          aria-hidden
        />
        <span
          className="relative inline-flex size-2 rounded-full"
          style={{ background: 'var(--accent)' }}
          aria-hidden
        />
      </span>
      {label}
      {progress && <span style={{ color: 'var(--fg-3)' }} className="font-mono">{progress}</span>}
    </span>
  );
}
