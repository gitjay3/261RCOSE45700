import { useState } from 'react';
import { clampRangeDays } from '@/lib/rangeDays';

interface RangeDaysInputProps {
  value: number;
  onCommit: (value: number) => void;
  ariaLabel: string;
  disabled?: boolean;
  className?: string;
}

export function RangeDaysInput({
  value,
  onCommit,
  ariaLabel,
  disabled = false,
  className = '',
}: RangeDaysInputProps) {
  const [draft, setDraft] = useState(String(value));
  const [prevValue, setPrevValue] = useState(value);

  if (prevValue !== value) {
    setPrevValue(value);
    setDraft(String(value));
  }

  const commit = () => {
    if (draft.trim() === '') {
      setDraft(String(value));
      return;
    }

    const next = clampRangeDays(Number(draft));
    setDraft(String(next));
    onCommit(next);
  };

  return (
    <label
      className={`inline-flex h-9 items-center gap-1 rounded-md border px-3 text-xs font-semibold ${className}`}
      style={{
        background: disabled ? 'var(--bg-sunk)' : 'var(--bg-elev)',
        borderColor: 'var(--border-1)',
        color: disabled ? 'var(--fg-3)' : 'var(--fg-2)',
      }}
    >
      최근
      <input
        type="text"
        inputMode="numeric"
        pattern="[0-9]*"
        value={draft}
        disabled={disabled}
        onChange={(event) => setDraft(event.target.value.replace(/\D/g, ''))}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === 'Enter') {
            event.currentTarget.blur();
          }
          if (event.key === 'Escape') {
            setDraft(String(value));
            event.currentTarget.blur();
          }
        }}
        className="h-7 w-16 rounded-[4px] border bg-transparent px-2 text-right font-mono text-xs disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
        style={{ borderColor: 'var(--border-1)', color: 'var(--fg)' }}
        aria-label={ariaLabel}
      />
      일
    </label>
  );
}
