import { describe, expect, it } from 'vitest';
import { formatDelta, formatPct } from '../src/lib/format';

describe('formatPct', () => {
  it('uses whole percent between 10 and 90', () => {
    expect(formatPct(0.536)).toBe('54%');
    expect(formatPct(0.1)).toBe('10%');
    expect(formatPct(0.9)).toBe('90%');
    expect(formatPct(0.896)).toBe('90%');
  });

  it('uses one decimal below 10% and above 90%', () => {
    expect(formatPct(0.048)).toBe('4.8%');
    expect(formatPct(0.934)).toBe('93.4%');
    expect(formatPct(0.001)).toBe('0.1%');
    expect(formatPct(0.999)).toBe('99.9%');
  });

  it('never shows 10.0% from rounding just below 10%', () => {
    expect(formatPct(0.0996)).toBe('10%');
  });

  it('never shows 0.0% or 100.0%', () => {
    expect(formatPct(0)).toBe('<0.1%');
    expect(formatPct(0.0004)).toBe('<0.1%');
    expect(formatPct(1)).toBe('>99.9%');
    expect(formatPct(0.99951)).toBe('>99.9%');
  });

  it('shows Qualified / Out only when certainty is passed in', () => {
    expect(formatPct(1, 'clinched')).toBe('Qualified');
    expect(formatPct(0, 'eliminated')).toBe('Out');
    expect(formatPct(1)).toBe('>99.9%');
  });
});

describe('formatDelta', () => {
  it('shows signed percentage points with a true minus sign', () => {
    expect(formatDelta(0.042)).toBe('+4.2');
    expect(formatDelta(-0.031)).toBe('−3.1');
  });

  it('returns null for changes that round to zero', () => {
    expect(formatDelta(0.0004)).toBeNull();
    expect(formatDelta(-0.0004)).toBeNull();
  });
});
