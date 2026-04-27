import { NavLink, Outlet } from 'react-router-dom';
import { useStatsQuery } from '@/api/stats';
import { FreshnessIndicator } from '@/components/common/FreshnessIndicator';
import { cn } from '@/lib/utils';

const NAV_ITEMS = [
  { to: '/', label: '대시보드', end: true },
  { to: '/detections', label: '탐지 목록', end: false },
  { to: '/stats', label: '통계', end: false },
] as const;

export function RootLayout() {
  // RootLayout이 useStatsQuery를 호출해 모든 페이지 헤더에서 freshness 표시.
  // TanStack Query 캐싱으로 Dashboard에서 또 호출해도 추가 fetch 발생하지 않음.
  const { dataUpdatedAt, isFetching } = useStatsQuery();

  return (
    <div className="bg-muted min-h-screen">
      <header className="bg-background sticky top-0 z-10 border-b">
        <div className="mx-auto flex h-15 max-w-7xl items-center justify-between px-8">
          <div className="flex items-center gap-8">
            <strong className="text-lg font-bold tracking-tight">Tracker</strong>
            <nav className="flex gap-1">
              {NAV_ITEMS.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    cn(
                      'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                      isActive
                        ? 'bg-muted text-foreground'
                        : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                    )
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>
          <FreshnessIndicator
            lastUpdatedAt={dataUpdatedAt}
            isFetching={isFetching}
          />
        </div>
      </header>
      <main className="mx-auto max-w-7xl">
        <Outlet />
      </main>
    </div>
  );
}
