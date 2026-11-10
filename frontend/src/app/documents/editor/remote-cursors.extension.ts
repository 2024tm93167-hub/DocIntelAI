import { Extension } from '@tiptap/core';
import { Plugin, PluginKey } from '@tiptap/pm/state';
import { Decoration, DecorationSet } from '@tiptap/pm/view';

import { PRESENCE_COLORS } from '../../core/services/document-ws.service';

export interface RemoteCursorInfo {
  user_id: string;
  name: string | null;
  /** Presence-assigned colour; falls back to a uid hash when absent. */
  color?: string;
  from: number;
  to: number;
  empty: boolean;
}

const cursorPluginKey = new PluginKey<DecorationSet>('remoteCursors');

/**
 * TipTap extension that renders remote collaborators' cursors and selections
 * as ProseMirror decorations.
 *
 * Usage: call `editor.storage.remoteCursors.setCursors(cursors)` to update,
 * or dispatch a transaction with meta `remoteCursors` containing the cursors map.
 */
export const RemoteCursors = Extension.create({
  name: 'remoteCursors',

  addStorage() {
    return {
      cursors: {} as Record<string, RemoteCursorInfo>,
      setCursors(_cursors: Record<string, RemoteCursorInfo>) {
        // Placeholder; the real setter is attached in the plugin view.
      },
    };
  },

  addProseMirrorPlugins() {
    const editor = this.editor;
    return [
      new Plugin<DecorationSet>({
        key: cursorPluginKey,
        state: {
          init() {
            return DecorationSet.empty;
          },
          apply(tr, oldState) {
            const meta = tr.getMeta(cursorPluginKey);
            if (meta !== undefined) {
              return meta;
            }
            return oldState.map(tr.mapping, tr.doc);
          },
        },
        props: {
          decorations(state) {
            return cursorPluginKey.getState(state);
          },
        },
        view(pluginView) {
          return {
            update() {
              // No-op; decorations are updated via setCursors
            },
          };
        },
      }),
    ];
  },

  onUpdate() {
    // Attach a setCursors helper to storage after the editor is ready
    const ed = this.editor;
    this.storage.setCursors = (cursors: Record<string, RemoteCursorInfo>) => {
      this.storage.cursors = cursors;
      const decorations: Decoration[] = [];
      const docSize = ed.state.doc.content.size;
      for (const uid of Object.keys(cursors)) {
        const cursor = cursors[uid];
        if (!cursor) continue;
        const from = Math.min(Math.max(cursor.from, 0), docSize);
        const to = Math.min(Math.max(cursor.to, 0), docSize);
        if (from > docSize || to > docSize) continue;
        const color = cursor.color ?? colorForUser(uid);
        const label = cursor.name || uid.slice(0, 6);

        if (cursor.empty || from === to) {
          // One widget containing both the caret bar and the name label — the
          // label is absolutely positioned inside the relative caret, so it
          // floats above the cursor instead of anchoring to the page.
          decorations.push(
            Decoration.widget(from, () => {
              const el = document.createElement('span');
              el.className = 'remote-cursor';
              el.style.borderLeftColor = color;
              el.dataset['userId'] = uid;
              const tag = document.createElement('span');
              tag.className = 'remote-cursor-label';
              tag.style.backgroundColor = color;
              tag.textContent = label;
              el.appendChild(tag);
              return el;
            }, { side: -1 }),
          );
        } else {
          decorations.push(
            Decoration.inline(from, to, {
              class: 'remote-selection',
              style: `background-color: ${color}33;`,
              'data-user-id': uid,
            }),
          );
          decorations.push(
            Decoration.widget(to, () => {
              const el = document.createElement('span');
              el.className = 'remote-cursor';
              el.style.borderLeftColor = color;
              el.dataset['userId'] = uid;
              const tag = document.createElement('span');
              tag.className = 'remote-cursor-label';
              tag.style.backgroundColor = color;
              tag.textContent = label;
              el.appendChild(tag);
              return el;
            }, { side: -1 }),
          );
        }
      }
      const decoSet = DecorationSet.create(ed.state.doc, decorations);
      const tr = ed.state.tr.setMeta(cursorPluginKey, decoSet);
      ed.view.dispatch(tr);
    };
  },
});

function colorForUser(uid: string): string {
  let hash = 0;
  for (let i = 0; i < uid.length; i++) {
    hash = ((hash << 5) - hash + uid.charCodeAt(i)) | 0;
  }
  return PRESENCE_COLORS[Math.abs(hash) % PRESENCE_COLORS.length];
}
