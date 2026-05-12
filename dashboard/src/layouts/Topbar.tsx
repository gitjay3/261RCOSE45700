import { useCallback, useEffect, useState } from 'react';
import { Menu, Moon, Sun } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ManualCrawlButton } from '@/components/tracker/ManualCrawlButton';
import { NewDetectionsBadge } from '@/components/tracker/NewDetectionsBadge';

type Theme = 'light' | 'dark';

function readInitialTheme(): Theme {
  if (typeof window === 'undefined') return 'light';
  // index.html 인라인 스크립트가 이미 data-theme을 설정 — 동일 우선순위 logic이지만
  // 신뢰원은 DOM. localStorage는 Safari Private Mode에서 throw 가능 → guarded.
  const fromDom = document.documentElement.getAttribute('data-theme');
  if (fromDom === 'dark' || fromDom === 'light') return fromDom;
  try {
    const saved = localStorage.getItem('theme');
    if (saved === 'dark' || saved === 'light') return saved;
  } catch {
    /* Private Mode → fallthrough */
  }
  if (window.matchMedia?.('(prefers-color-scheme: dark)').matches) return 'dark';
  return 'light';
}

interface TopbarProps {
  onMenuClick: () => void;
}

export function Topbar({ onMenuClick }: TopbarProps) {
  const [theme, setTheme] = useState<Theme>(readInitialTheme);
  const [triggerAt, setTriggerAt] = useState<number | null>(null);
  const dismissBadge = useCallback(() => setTriggerAt(null), []);

  useEffect(() => {
    // 변경 없는 쓰기 차단 — StrictMode 이중 effect / 초기 mount no-op 모두 흡수
    if (document.documentElement.getAttribute('data-theme') !== theme) {
      document.documentElement.setAttribute('data-theme', theme);
    }
    try {
      if (localStorage.getItem('theme') !== theme) {
        localStorage.setItem('theme', theme);
      }
    } catch {
      /* localStorage 쓰기 실패 무시 */
    }
  }, [theme]);

  return (
    <div
      className="flex items-center gap-2.5 border-b"
      style={{
        height: 'var(--h-topbar)',
        padding: '0 var(--pad-topbar-x)',
        borderColor: 'var(--border-1)',
      }}
    >
      <Button
        type="button"
        variant="outline"
        size="icon"
        onClick={onMenuClick}
        aria-label="메뉴 열기"
        className="lg:hidden"
      >
        <Menu />
      </Button>
      <div className="ml-auto flex items-center gap-2.5">
        {triggerAt !== null && (
          <NewDetectionsBadge triggerAt={triggerAt} onDismiss={dismissBadge} />
        )}
        <ManualCrawlButton onTriggerSuccess={() => setTriggerAt(Date.now())} />
        <ThemeToggle theme={theme} onToggle={() => setTheme(theme === 'dark' ? 'light' : 'dark')} />
      </div>
    </div>
  );
}

function ThemeToggle({ theme, onToggle }: { theme: Theme; onToggle: () => void }) {
  const Icon = theme === 'dark' ? Sun : Moon;
  return (
    <Button
      type="button"
      variant="outline"
      size="icon"
      onClick={onToggle}
      aria-label="테마 전환"
      title={theme === 'dark' ? '라이트로 전환' : '다크로 전환'}
    >
      <Icon />
    </Button>
  );
}
