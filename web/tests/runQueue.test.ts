import { describe, expect, it } from 'vitest';
import { createRunQueue } from '../src/lib/runQueue';

describe('createRunQueue', () => {
  it('keeps one job in flight and only the newest waiting one', () => {
    const sent: number[] = [];
    const q = createRunQueue<number>((m) => sent.push(m));
    q.submit(1); // starts at once
    q.submit(2); // waits
    q.submit(3); // replaces 2
    q.submit(4); // replaces 3
    expect(sent).toEqual([1]);
    q.done(); // 1 finished -> newest waiting job goes
    expect(sent).toEqual([1, 4]);
    q.done();
    expect(sent).toEqual([1, 4]);
    q.submit(5); // idle again: starts at once
    expect(sent).toEqual([1, 4, 5]);
  });

  it('a stray completion while idle does not send anything', () => {
    const sent: number[] = [];
    const q = createRunQueue<number>((m) => sent.push(m));
    q.done();
    expect(sent).toEqual([]);
  });
});
