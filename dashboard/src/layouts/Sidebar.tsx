import { NavLink } from 'react-router-dom';
import { LayoutDashboard, ListChecks, BarChart3, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

const NAV_ITEMS = [
  { to: '/', label: '대시보드', end: true, Icon: LayoutDashboard },
  { to: '/detections', label: '탐지 목록', end: false, Icon: ListChecks },
  { to: '/stats', label: '통계', end: false, Icon: BarChart3 },
] as const;

interface SidebarProps {
  drawerOpen: boolean;
  onClose: () => void;
}

export function Sidebar({ drawerOpen, onClose }: SidebarProps) {
  return (
    <>
      {/* Backdrop — mobile drawer 전용. lg 이상에서는 sidebar가 grid cell이라 backdrop 불필요. */}
      <div
        aria-hidden
        onClick={onClose}
        className={cn(
          'fixed inset-0 z-40 bg-black/40 backdrop-blur-sm transition-opacity lg:hidden',
          drawerOpen ? 'opacity-100' : 'pointer-events-none opacity-0',
        )}
      />

      <aside
        aria-label="주 탐색"
        className={cn(
          // mobile: fixed drawer with slide-in animation
          'fixed inset-y-0 left-0 z-50 w-72 transform border-r transition-transform duration-200',
          // lg: 원위치로 — sticky top-0 h-screen, grid cell 자동 너비
          'lg:sticky lg:top-0 lg:z-auto lg:h-screen lg:w-auto lg:transform-none lg:transition-none',
          drawerOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0',
        )}
        style={{
          background: 'var(--bg-sunk)',
          borderColor: 'var(--border-1)',
          // drawer 모드(< lg)에서 상단 노치 + 하단 홈 인디케이터 침범 회피.
          // lg 이상에선 safe-area=0이라 영향 없음.
          padding: 'calc(clamp(16px, 1.5vw, 28px) + var(--sat)) clamp(10px, 0.8vw, 16px) calc(clamp(16px, 1.5vw, 28px) + var(--sab))',
        }}
      >
        {/* 헤더 — 로고 + 닫기 (모바일만) */}
        <div className="mb-4 flex items-center justify-between px-2">
          <div
            className="flex items-center gap-2.5 text-base font-semibold"
            style={{ letterSpacing: 'var(--tracking-tight)' }}
          >
            <span
              className="font-mono inline-flex size-6 items-center justify-center rounded-[5px] text-xs font-bold"
              style={{ background: 'var(--fg)', color: 'var(--bg)' }}
            >
              T
            </span>
            <span>Tracker</span>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={onClose}
            aria-label="메뉴 닫기"
            className="lg:hidden"
          >
            <X />
          </Button>
        </div>
        <nav className="flex flex-col gap-0.5">
          {NAV_ITEMS.map(({ to, label, end, Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-[5px] px-3 py-2.5 text-sm font-medium no-underline transition-colors',
                  // 색상은 className만으로 처리 — inline style이 hover를 가로채지 않게.
                  isActive
                    ? 'bg-bg-elev text-fg'
                    : 'text-fg-2 hover:bg-bg-overlay hover:text-fg',
                )
              }
            >
              <Icon className="size-4 shrink-0 opacity-85" />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>
    </>
  );
}
