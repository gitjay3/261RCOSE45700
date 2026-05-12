import { describe, expect, it } from 'vitest';
import { formatScore, severityOf } from './severity';

describe('severityOf', () => {
  it('returns high for score >= 0.8', () => {
    expect(severityOf(0.8)).toBe('high');
    expect(severityOf(0.95)).toBe('high');
    expect(severityOf(1)).toBe('high');
  });

  it('returns medium for 0.5 <= score < 0.8', () => {
    expect(severityOf(0.5)).toBe('medium');
    expect(severityOf(0.7)).toBe('medium');
    expect(severityOf(0.799)).toBe('medium');
  });

  it('returns low for score < 0.5', () => {
    expect(severityOf(0)).toBe('low');
    expect(severityOf(0.49)).toBe('low');
  });

  it('clamps out-of-range inputs', () => {
    expect(severityOf(-5)).toBe('low');
    expect(severityOf(99)).toBe('high');
  });

  it('returns low for non-finite inputs', () => {
    expect(severityOf(NaN)).toBe('low');
    expect(severityOf(Infinity)).toBe('low');
  });
});

describe('formatScore', () => {
  it('formats two-decimal without leading zero', () => {
    expect(formatScore(0.95)).toBe('.95');
    expect(formatScore(0.5)).toBe('.50');
    expect(formatScore(0)).toBe('.00');
  });

  it('caps at .99 (width protection)', () => {
    expect(formatScore(1)).toBe('.99');
    expect(formatScore(1.5)).toBe('.99');
  });

  it('returns dash for non-finite', () => {
    expect(formatScore(NaN)).toBe('—');
  });
});
