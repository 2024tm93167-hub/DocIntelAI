import { Extension } from '@tiptap/core';

export interface IndentOptions {
  types: string[];
  minLevel: number;
  maxLevel: number;
  indentSize: number;
}

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    indent: {
      indent: () => ReturnType;
      outdent: () => ReturnType;
    };
  }
}

/**
 * Adds Word/Google-Docs-style paragraph indentation.
 * Applies a `margin-left` inline style to block nodes (paragraph/heading)
 * based on an `indent` attribute, with `indent()` / `outdent()` commands.
 */
export const Indent = Extension.create<IndentOptions>({
  name: 'indent',

  addOptions() {
    return {
      types: ['heading', 'paragraph'],
      minLevel: 0,
      maxLevel: 8,
      indentSize: 24,
    };
  },

  addGlobalAttributes() {
    const { types, indentSize } = this.options;
    return [
      {
        types,
        attributes: {
          indent: {
            default: 0,
            renderHTML: (attributes) => {
              const level = Number(attributes['indent']) || 0;
              if (!level) return {};
              return { style: `margin-left: ${level * indentSize}px` };
            },
            parseHTML: (element) => {
              const margin = parseInt(element.style.marginLeft || '0', 10);
              return margin > 0 ? Math.round(margin / indentSize) : 0;
            },
          },
        },
      },
    ];
  },

  addCommands() {
    const { types, minLevel, maxLevel } = this.options;

    const applyIndent =
      (delta: number) =>
      ({ tr, state, dispatch }: { tr: any; state: any; dispatch: ((tr: any) => void) | undefined }) => {
        const { selection } = state;
        let changed = false;

        state.doc.nodesBetween(selection.from, selection.to, (node: any, pos: number) => {
          if (types.includes(node.type.name)) {
            const current = Number(node.attrs['indent']) || 0;
            const next = Math.min(maxLevel, Math.max(minLevel, current + delta));
            if (next !== current) {
              tr.setNodeMarkup(pos, undefined, { ...node.attrs, indent: next });
              changed = true;
            }
          }
        });

        if (changed && dispatch) dispatch(tr);
        return changed;
      };

    return {
      indent: () => applyIndent(1),
      outdent: () => applyIndent(-1),
    };
  },
});
