import { Fragment, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Kbd } from '@/components/ui/kbd';
import { useShortcut } from '@/lib/shortcuts';

interface ShortcutEntry {
  keys: readonly string[];
  label: string;
  scope?: string;
}

const SHORTCUTS: readonly ShortcutEntry[] = [
  { keys: ['?'], label: '단축키 안내', scope: '전역' },
  { keys: ['g', 'd'], label: '대시보드', scope: '전역' },
  { keys: ['g', 'l'], label: '탐지 목록', scope: '전역' },
  { keys: ['g', 's'], label: '통계', scope: '전역' },
  { keys: ['g', 't'], label: '수동 크롤링', scope: '전역' },
  { keys: ['j'], label: '다음 행', scope: '목록' },
  { keys: ['k'], label: '이전 행', scope: '목록' },
  { keys: ['Enter'], label: '상세 열기', scope: '목록' },
  { keys: ['o'], label: '원본 게시글 열기', scope: '상세' },
  { keys: ['c'], label: '링크 복사', scope: '상세' },
  { keys: ['Esc'], label: '목록으로', scope: '상세' },
] as const;

export function ShortcutsCheatsheet() {
  const [open, setOpen] = useState(false);
  useShortcut('?', () => setOpen(true));

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>키보드 단축키</DialogTitle>
          <DialogDescription>
            화살표·마우스 없이 운영 가능. 입력 필드 focus 시 단축키는 자동 비활성.
          </DialogDescription>
        </DialogHeader>
        <ul className="flex flex-col gap-1">
          {SHORTCUTS.map((s) => (
            <li
              key={s.keys.join('+')}
              className="text-fg-2 grid items-baseline gap-3 border-b py-2 text-sm last:border-b-0"
              style={{ gridTemplateColumns: '110px 1fr 70px', borderColor: 'var(--border-1)' }}
            >
              <span className="flex gap-1">
                {s.keys.map((k, i) => (
                  <Fragment key={k}>
                    {i > 0 && (
                      <span className="text-fg-3 font-mono text-xs">+</span>
                    )}
                    <Kbd variant="outline" size="md">{k}</Kbd>
                  </Fragment>
                ))}
              </span>
              <span>{s.label}</span>
              <span className="text-fg-3 text-right font-mono text-xs">
                {s.scope}
              </span>
            </li>
          ))}
        </ul>
      </DialogContent>
    </Dialog>
  );
}
