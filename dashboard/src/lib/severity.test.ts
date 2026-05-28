import { describe, expect, it } from 'vitest';
import { formatScore, severityOf, severityOfDetection, severityOfTier } from './severity';

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

describe('severityOfTier', () => {
  it('maps T1/T2 to high, T3 to medium, and T4 to low', () => {
    expect(severityOfTier('T1')).toBe('high');
    expect(severityOfTier('T2')).toBe('high');
    expect(severityOfTier('T3')).toBe('medium');
    expect(severityOfTier('T4')).toBe('low');
  });

  it('keeps legal detections low regardless of tier', () => {
    expect(severityOfDetection({ tier: 'T1', isIllegal: false })).toBe('low');
  });

  it('falls back to confidence for illegal detections without tier', () => {
    expect(severityOfDetection({ confidence: 0.95, isIllegal: true })).toBe('high');
    expect(severityOfDetection({ confidence: 0.7, isIllegal: true })).toBe('medium');
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
