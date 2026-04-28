import { useEffect, useState } from 'react';
import { Sun, Moon } from 'lucide-react';
import { ManualCrawlButton } from '@/components/tracker/ManualCrawlButton';

type Theme = 'light' | 'dark';

export function Topbar() {
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof window === 'undefined') return 'light';
    const saved = localStorage.getItem('theme');
    return (saved === 'dark' ? 'dark' : 'light') as Theme;
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  return (
    <div
      className="flex items-center justify-end gap-2.5 border-b"
      style={{
        height: 'var(--h-topbar)',
        padding: '0 var(--pad-topbar-x)',
        borderColor: 'var(--border-1)',
      }}
    >
      <ManualCrawlButton />
      <ThemeToggle theme={theme} onToggle={() => setTheme(theme === 'dark' ? 'light' : 'dark')} />
    </div>
  );
}

function ThemeToggle({ theme, onToggle }: { theme: Theme; onToggle: () => void }) {
  const Icon = theme === 'dark' ? Sun : Moon;
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label="테마 전환"
      title={theme === 'dark' ? '라이트로 전환' : '다크로 전환'}
      className="inline-flex size-8 cursor-pointer items-center justify-center rounded-md border bg-transparent transition-colors"
      style={{
        borderColor: 'var(--border-1)',
        color: 'var(--fg-2)',
      }}
    >
      <Icon className="size-3.5" />
    </button>
  );
}
