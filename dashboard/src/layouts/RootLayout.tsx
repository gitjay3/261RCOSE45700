import { Suspense, useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';
import { RightRail } from './RightRail';
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import { ShortcutsCheatsheet } from '@/components/tracker/ShortcutsCheatsheet';
import { useShortcut } from '@/lib/shortcuts';

/**
 * 3-column 레이아웃 (≥ lg) — Sidebar | Main(Topbar + Outlet) | RightRail
 * mockup: ux-direction-a-v3-with-rail.html 와 동일 구조.
 *
 * < lg: Sidebar는 fixed drawer (Topbar 햄버거로 토글), RightRail은 숨김.
 * 라우트 전환 시 drawer 자동 닫힘.
 */
export function RootLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  useShortcut('g+d', () => navigate('/'));
  useShortcut('g+l', () => navigate('/detections'));
  useShortcut('g+s', () => navigate('/stats'));

  const [drawerOpen, setDrawerOpen] = useState(false);
  // "previous state in render" — 경로 바뀌면 drawer 닫힘 (effect 회피, DetectionListPage 패턴과 동일).
  const [prevPath, setPrevPath] = useState(location.pathname);
  if (prevPath !== location.pathname) {
    setPrevPath(location.pathname);
    if (drawerOpen) setDrawerOpen(false);
  }

  return (
    <div className="grid min-h-screen grid-cols-1 lg:grid-cols-[clamp(240px,18vw,400px)_minmax(0,1fr)_clamp(240px,17vw,340px)]">
      <Sidebar drawerOpen={drawerOpen} onClose={() => setDrawerOpen(false)} />
      <main className="flex min-w-0 flex-col">
        <Topbar onMenuClick={() => setDrawerOpen(true)} />
        <Suspense
          fallback={
            <div className="flex min-h-[60vh] items-center justify-center p-8">
              <LoadingSpinner size="lg" />
            </div>
          }
        >
          <Outlet />
        </Suspense>
      </main>
      <RightRail />
      <ShortcutsCheatsheet />
    </div>
  );
}
