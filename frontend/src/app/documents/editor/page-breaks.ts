import { Extension } from '@tiptap/core';
import { Plugin, PluginKey } from '@tiptap/pm/state';
import { Decoration, DecorationSet } from '@tiptap/pm/view';
import type { EditorView } from '@tiptap/pm/view';

/**
 * Real pagination for the editor: measures each top-level block's rendered
 * height (and each list item inside list blocks) and inserts non-editable
 * "page gap" decorations at boundaries that would otherwise be split across a
 * page edge. Each gap renders the rest of the current page's whitespace, a
 * gray workspace band, and the next page's top margin — so every page gets
 * real margins, no block is sliced, and long lists flow across pages instead
 * of leaving a huge void.
 *
 * The decoration layer is presentation-only: the stored document JSON is never
 * touched, so autosave, undo/redo, selections and collaboration are unaffected.
 */

export const PAGE_HEIGHT = 1120;        // matches .editor-canvas min-height
export const PAGE_MARGIN_V = 80;        // top/bottom page margin (canvas padding)
export const PAGE_GAP_BAND = 48;        // gray band shown between pages
export const PAGE_CONTENT_HEIGHT = PAGE_HEIGHT - PAGE_MARGIN_V * 2; // 960
export const GAP_CLASS = 'pm-page-gap';
export const BAND_CLASS = 'pm-page-gap-band';
const LIST_TYPES = new Set(['bulletList', 'orderedList', 'taskList']);

/** A position in the doc where a page break is allowed to land. */
export interface PagePoint {
  /** Doc position the gap widget is inserted at when this point is pushed. */
  pos: number;
  /** Distance from this point's top edge to the next point's top edge (px). */
  stride: number;
  /** Headings keep with the following block — a break is pulled before them. */
  keepWithNext?: boolean;
}

export interface PageGapSpec {
  /** Index into the points array where the gap lands. */
  index: number;
  /** Doc position of the gap widget. */
  pos: number;
  /** Total spacer height in px. */
  height: number;
  /** Offset inside the spacer where the gray band starts, in px. */
  bandTop: number;
  /** Gray band height in px. */
  bandHeight: number;
}

/**
 * Given breakable points with measured strides, return the page gaps needed so
 * no fitting segment crosses a page boundary. Pure function — unit-testable.
 * `keepWithNext` points (headings) pull an upcoming break back so a heading is
 * never orphaned at the bottom of a page.
 */
export function computePageGaps(
  points: PagePoint[],
  contentH: number,
  marginV: number,
  bandH: number,
): PageGapSpec[] {
  const gaps: PageGapSpec[] = [];
  const entries = new Array<number>(points.length);
  const gapBefore = new Set<number>();
  // Small epsilon: sub-pixel measurement noise shouldn't flip a boundary
  // decision between passes (2px of overhang hides in the bottom margin).
  const EPS = 2;
  let used = 0;
  for (let i = 0; i < points.length; i++) {
    const h = points[i].stride;
    entries[i] = used;
    if (h <= 0) continue;
    if (used + h > contentH + EPS && h <= contentH) {
      // Pull the break back over trailing keep-with-next points (headings) so
      // they start the new page together with what follows them.
      let k = i;
      while (k - 1 >= 0 && points[k - 1].keepWithNext && !gapBefore.has(k - 1)) k--;
      const fill = contentH - entries[k];
      gaps.push({
        index: k,
        pos: points[k].pos,
        height: fill + marginV * 2 + bandH,
        bandTop: fill + marginV,
        bandHeight: bandH,
      });
      gapBefore.add(k);
      // Points k..i all start the new page; used = their combined strides.
      used = entries[i] + h - entries[k];
    } else {
      used += h;
      // Oversized segments (taller than a page) straddle the boundary
      // invisibly — a single DOM node can't be split, so only the wrap
      // position is kept. An exactly-full page keeps used === contentH so the
      // NEXT point gets a gap.
      if (used > contentH) used %= contentH;
    }
  }
  return gaps;
}

interface GapMeasurement {
  set: DecorationSet;
  signature: string;
  pageCount: number;
}

const pageBreaksKey = new PluginKey<DecorationSet>('pageBreaks');

interface RawPoint {
  pos: number;
  el: HTMLElement | null;
  keepWithNext: boolean;
}

/**
 * Flatten the document into breakable points: one per top-level block, plus
 * one per item inside list blocks (a list can break between items). The first
 * list item maps to the list's own position so a break before item 0 pushes
 * the whole list instead of leaving an empty list fragment.
 */
function collectRawPoints(view: EditorView): RawPoint[] {
  const points: RawPoint[] = [];
  view.state.doc.forEach((node, offset) => {
    const el = view.nodeDOM(offset);
    const keepWithNext = node.type.name === 'heading';
    if (!LIST_TYPES.has(node.type.name) || node.childCount === 0) {
      points.push({ pos: offset, el: el instanceof HTMLElement ? el : null, keepWithNext });
      return;
    }
    let added = false;
    node.forEach((_child, childOffset) => {
      const liPos = offset + 1 + childOffset;
      const liDom = view.nodeDOM(liPos);
      // The first item's gap widget lands before the <ul> itself (pos = offset),
      // so measure its bleed from the list element — the <li> is indented
      // inside the list and would overshoot the page edge.
      points.push({
        pos: added ? liPos : offset,
        el: added
          ? (liDom instanceof HTMLElement ? liDom : null)
          : (el instanceof HTMLElement ? el : null),
        keepWithNext: false,
      });
      added = true;
    });
  });
  return points;
}

/**
 * Find the injected gap spacer that precedes this point's DOM edge, or null.
 * The spacer is a sibling of the boundary element — for a point mapped to a
 * nested element (e.g. the first <li> of a pushed list) it is a sibling of an
 * ancestor, so climb while there is no previous sibling.
 */
function spacerBefore(el: HTMLElement, root: HTMLElement): HTMLElement | null {
  let probe: HTMLElement | null = el;
  while (probe && probe !== root) {
    const sib = probe.previousElementSibling as HTMLElement | null;
    if (sib) return sib.classList.contains(GAP_CLASS) ? sib : null;
    probe = probe.parentElement;
  }
  return null;
}

function measureStrides(view: EditorView, points: RawPoint[], zoom: number): number[] {
  return points.map((p, i) => {
    const el = p.el;
    const next = points[i + 1]?.el;
    if (!el) return 0;
    if (!next) return el.offsetHeight;
    // Stride = distance to the next point's top edge (captures collapsed
    // margins), minus any previously-injected gap spacer sitting between them.
    let stride = next.offsetTop - el.offsetTop;
    const spacer = spacerBefore(next, view.dom as HTMLElement);
    if (spacer) {
      stride -= spacer.offsetHeight;
      // A spacer div also breaks margin collapsing between its neighbours
      // (mb + mt instead of max(mb, mt)) — subtract that overlap too or the
      // measured stride grows on every pass and pagination oscillates.
      // Margins from getComputedStyle are unzoomed; strides are zoomed.
      const before = spacer.previousElementSibling as HTMLElement | null;
      const after = spacer.nextElementSibling as HTMLElement | null;
      const mb = before ? parseFloat(getComputedStyle(before).marginBottom) || 0 : 0;
      const mt = after ? parseFloat(getComputedStyle(after).marginTop) || 0 : 0;
      stride -= Math.min(mb, mt) * zoom;
    }
    return Math.max(0, stride);
  });
}

function measurePageGaps(view: EditorView): GapMeasurement {
  const empty: GapMeasurement = { set: DecorationSet.empty, signature: 'none', pageCount: 1 };
  const dom = view.dom as HTMLElement;
  if (!dom.isConnected || dom.children.length === 0) return empty;

  const canvas = dom.closest('.editor-canvas') as HTMLElement | null;
  const cs = canvas ? getComputedStyle(canvas) : null;
  // CSS zoom scales layout metrics; normalize strides to unzoomed px.
  const zoom = cs ? parseFloat(cs.zoom) || 1 : 1;
  const padTop = cs ? parseFloat(cs.paddingTop) || PAGE_MARGIN_V : PAGE_MARGIN_V;
  const padBottom = cs ? parseFloat(cs.paddingBottom) || PAGE_MARGIN_V : PAGE_MARGIN_V;
  const pageH = cs ? parseFloat(cs.minHeight) || PAGE_HEIGHT : PAGE_HEIGHT;
  const contentH = Math.max(160, pageH - padTop - padBottom);
  const canvasRect = canvas?.getBoundingClientRect();

  const points = collectRawPoints(view);
  const strides = measureStrides(view, points, zoom).map(s => s / zoom);
  const specs = computePageGaps(
    points.map((p, i) => ({ pos: p.pos, stride: strides[i], keepWithNext: p.keepWithNext })),
    contentH, PAGE_MARGIN_V, PAGE_GAP_BAND,
  );

  const decorations: Decoration[] = [];
  for (const spec of specs) {
    const el = points[spec.index]?.el;
    // Bleed the spacer over the canvas padding + border so the gray band
    // reads as the workspace showing between two separate sheets. Left/right
    // measured independently since list items are indented inside the list.
    const elRect = el?.getBoundingClientRect();
    const bleedL = elRect && canvasRect ? (elRect.left - canvasRect.left) / zoom : 0;
    const bleedR = elRect && canvasRect ? (canvasRect.right - elRect.right) / zoom : 0;
    decorations.push(
      Decoration.widget(
        spec.pos,
        () => {
          const gap = document.createElement('div');
          gap.className = GAP_CLASS;
          gap.contentEditable = 'false';
          gap.style.height = `${spec.height}px`;
          gap.style.marginLeft = `${-bleedL}px`;
          gap.style.marginRight = `${-bleedR}px`;
          const band = document.createElement('div');
          band.className = BAND_CLASS;
          band.style.top = `${spec.bandTop}px`;
          band.style.height = `${spec.bandHeight}px`;
          gap.appendChild(band);
          return gap;
        },
        { side: -1, ignoreSelection: true, key: `${GAP_CLASS}-${spec.pos}-${Math.round(spec.height)}` },
      ),
    );
  }

  return {
    set: DecorationSet.create(view.state.doc, decorations),
    signature: specs.map(s => `${s.pos}:${Math.round(s.height)}`).join('|'),
    pageCount: specs.length + 1,
  };
}

export interface PageBreaksOptions {
  /** Called with the measured page count after every re-layout. */
  onPageCount?: (count: number) => void;
}

export interface PageBreaksStorage {
  pageCount: number;
  refresh: () => void;
}

export const PageBreaks = Extension.create<PageBreaksOptions, PageBreaksStorage>({
  name: 'pageBreaks',

  addOptions() {
    return {
      onPageCount: undefined,
    };
  },

  addStorage() {
    return {
      pageCount: 1,
      refresh() { /* bound in plugin view */ },
    };
  },

  addProseMirrorPlugins() {
    const editor = this.editor;
    const options = this.options;
    return [
      new Plugin<DecorationSet>({
        key: pageBreaksKey,
        state: {
          init: () => DecorationSet.empty,
          apply(tr, set) {
            const meta = tr.getMeta(pageBreaksKey);
            if (meta instanceof DecorationSet) return meta;
            return set.map(tr.mapping, tr.doc);
          },
        },
        props: {
          decorations(state) {
            return pageBreaksKey.getState(state);
          },
        },
        view(view) {
          let raf = 0;
          let signature = '';

          const storage = editor.storage as { pageBreaks?: PageBreaksStorage };
          let lastPageCount = 0;
          const measure = () => {
            raf = 0;
            if (view.isDestroyed) return;
            try {
              const { set, signature: sig, pageCount } = measurePageGaps(view);
              if (storage.pageBreaks) storage.pageBreaks.pageCount = pageCount;
              if (pageCount !== lastPageCount) {
                lastPageCount = pageCount;
                options.onPageCount?.(pageCount);
              }
              if (sig === signature) return;
              signature = sig;
              view.dispatch(view.state.tr.setMeta(pageBreaksKey, set));
            } catch {
              // Layout not measurable yet (e.g. mid-teardown) — retry on next tick.
            }
          };
          const schedule = () => {
            if (!raf) raf = requestAnimationFrame(measure);
          };
          // Doc changes are debounced so bands don't redraw on every keystroke;
          // mapped decorations keep gaps roughly positioned until the re-measure.
          let debounce: ReturnType<typeof setTimeout> | undefined;
          const scheduleDebounced = () => {
            if (debounce) return;
            debounce = setTimeout(() => { debounce = undefined; schedule(); }, 140);
          };

          const observer = new ResizeObserver(schedule);
          observer.observe(view.dom);
          document.fonts?.ready.then(schedule).catch(() => undefined);
          if (storage.pageBreaks) storage.pageBreaks.refresh = schedule;
          schedule();

          return {
            update(v, prev) {
              if (v.state.doc !== prev.doc) scheduleDebounced();
            },
            destroy() {
              if (debounce) clearTimeout(debounce);
              if (raf) cancelAnimationFrame(raf);
              observer.disconnect();
            },
          };
        },
      }),
    ];
  },
});
