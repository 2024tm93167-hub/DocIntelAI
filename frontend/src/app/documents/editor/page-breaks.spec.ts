import { describe, expect, it } from 'vitest';

import { computePageGaps, PAGE_CONTENT_HEIGHT, PAGE_GAP_BAND, PAGE_MARGIN_V, PagePoint } from './page-breaks';

const CONTENT = PAGE_CONTENT_HEIGHT; // 960
const MARGIN = PAGE_MARGIN_V;        // 80
const BAND = PAGE_GAP_BAND;          // 48

function pts(...strides: number[]): PagePoint[] {
  return strides.map((stride, i) => ({ pos: i * 100, stride }));
}

describe('computePageGaps', () => {
  it('returns no gaps when all content fits on one page', () => {
    expect(computePageGaps(pts(300, 200, 400), CONTENT, MARGIN, BAND)).toEqual([]);
  });

  it('inserts a gap before the point that would cross the boundary', () => {
    // 700 used; next (400) would land at 1100 > 960 → pushed to page 2.
    const gaps = computePageGaps(pts(700, 400, 100), CONTENT, MARGIN, BAND);
    expect(gaps).toHaveLength(1);
    expect(gaps[0].index).toBe(1);
    expect(gaps[0].pos).toBe(100);
    expect(gaps[0].height).toBe(260 + 2 * MARGIN + BAND); // fill + margins + band
    expect(gaps[0].bandTop).toBe(260 + MARGIN);           // band sits after prev-page margin
  });

  it('produces a gap per page boundary on multi-page documents', () => {
    const gaps = computePageGaps(pts(600, 500, 500, 200), CONTENT, MARGIN, BAND);
    // point1 pushed (600+500 > 960), point2 pushed again (500+500 > 960)
    expect(gaps.map(g => g.index)).toEqual([1, 2]);
    expect(gaps[1].height).toBe(460 + 2 * MARGIN + BAND);
  });

  it('does not slice an oversized segment taller than a page', () => {
    const gaps = computePageGaps(pts(200, 1500, 100), CONTENT, MARGIN, BAND);
    // 200 + 1500 > 960 but 1500 > 960 → straddles invisibly, no gap before it.
    // After straddling, used = (200+1500) % 960 = 740; +100 fits.
    expect(gaps).toEqual([]);
  });

  it('keeps tracking page position after an oversized segment', () => {
    // used after straddle = 740; next point 400 → 1140 > 960 → gap before index 2.
    const gaps = computePageGaps(pts(200, 1500, 400), CONTENT, MARGIN, BAND);
    expect(gaps).toHaveLength(1);
    expect(gaps[0].index).toBe(2);
    expect(gaps[0].height).toBe(220 + 2 * MARGIN + BAND);
  });

  it('emits a gap after a page that is exactly full', () => {
    const gaps = computePageGaps(pts(960, 100), CONTENT, MARGIN, BAND);
    expect(gaps.map(g => g.index)).toEqual([1]);
    expect(gaps[0].height).toBe(0 + 2 * MARGIN + BAND);
  });

  it('ignores zero-height points', () => {
    expect(computePageGaps(pts(0, 500, 0, 100), CONTENT, MARGIN, BAND)).toEqual([]);
  });

  it('pulls the break back over a keep-with-next heading', () => {
    const points: PagePoint[] = [
      { pos: 0, stride: 900 },                              // long paragraph
      { pos: 10, stride: 30, keepWithNext: true },          // heading at page bottom
      { pos: 20, stride: 50 },                              // paragraph that overflows
    ];
    const gaps = computePageGaps(points, CONTENT, MARGIN, BAND);
    // Break lands before the heading (pos 10), not before the paragraph.
    expect(gaps).toHaveLength(1);
    expect(gaps[0].index).toBe(1);
    expect(gaps[0].pos).toBe(10);
    expect(gaps[0].height).toBe(60 + 2 * MARGIN + BAND);    // fill = 960 - 900
  });

  it('walks back over consecutive headings', () => {
    const points: PagePoint[] = [
      { pos: 0, stride: 890 },
      { pos: 10, stride: 30, keepWithNext: true },          // h2
      { pos: 20, stride: 25, keepWithNext: true },          // h3 nested heading
      { pos: 30, stride: 60 },                              // paragraph
    ];
    const gaps = computePageGaps(points, CONTENT, MARGIN, BAND);
    expect(gaps).toHaveLength(1);
    expect(gaps[0].index).toBe(1);                          // break before the h2
    expect(gaps[0].pos).toBe(10);
    expect(gaps[0].height).toBe(70 + 2 * MARGIN + BAND);    // fill = 960 - 890
  });

  it('does not pull a break back across an existing gap', () => {
    const points: PagePoint[] = [
      { pos: 0, stride: 900 },
      { pos: 10, stride: 100, keepWithNext: true },         // pushed (900+100>960) → gap at 1
      { pos: 20, stride: 900 },                             // 100+900>960 → gap at 2
      { pos: 30, stride: 30, keepWithNext: true },          // fits: 900+30<=960 on page 3
      { pos: 40, stride: 960 },                             // 930+960>960 → gap pulled back to 3
      { pos: 50, stride: 50 },                              // 960+50>960 → gap at 5
    ];
    const gaps = computePageGaps(points, CONTENT, MARGIN, BAND);
    expect(gaps.map(g => g.index)).toEqual([1, 2, 3, 5]);
  });

  it('leaves top whitespace equal to fill + margins, not a raw seam', () => {
    const gaps = computePageGaps(pts(900, 200), CONTENT, MARGIN, BAND);
    expect(gaps[0].height - gaps[0].bandHeight - (960 - 900)).toBe(2 * MARGIN);
  });
});
