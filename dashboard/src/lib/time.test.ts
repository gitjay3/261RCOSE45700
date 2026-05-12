import { describe, expect, it } from 'vitest';
import { formatRelativeTime } from './time';

describe('formatRelativeTime', () => {
  it('accepts ISO string', () => {
    const past = new Date(Date.now() - 5 * 60_000).toISOString();
    expect(formatRelativeTime(past)).toMatch(/전$/);
  });

  it('accepts ms timestamp (number)', () => {
    const ms = Date.now() - 60_000;
    expect(formatRelativeTime(ms)).toMatch(/전$/);
  });

  it('accepts Date instance', () => {
    const d = new Date(Date.now() - 3_600_000);
    expect(formatRelativeTime(d)).toMatch(/전$/);
  });

  it('returns dash for invalid ISO string', () => {
    expect(formatRelativeTime('not-a-date')).toBe('—');
  });

  it('returns dash for NaN', () => {
    expect(formatRelativeTime(NaN)).toBe('—');
  });
});
