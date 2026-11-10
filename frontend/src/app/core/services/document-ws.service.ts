import { Injectable, signal, NgZone, inject } from '@angular/core';
import { environment } from '../../../environments/environment';

export interface PresenceUser {
  user_id: string;
  name: string | null;
  email: string | null;
  /** Assigned per-user cursor/avatar colour, derived from presence order. */
  color?: string;
}

/**
 * Deterministic per-user palette, assigned by each user's position in the
 * presence list. The server sends the same ordered list to every client, so
 * a given collaborator renders in the same colour on every screen.
 */
export const PRESENCE_COLORS = [
  '#ef4444', '#f97316', '#eab308', '#22c55e',
  '#06b6d4', '#3b82f6', '#8b5cf6', '#ec4899',
];

export type WsEventType = 'presence' | 'presence_list' | 'document_updated' | 'version_created' | 'cursor';

export interface RemoteCursor {
  user_id: string;
  name: string | null;
  color?: string;
  from: number;
  to: number;
  empty: boolean;
}

export interface WsMessage {
  type: WsEventType;
  users?: PresenceUser[];
  user_id?: string;
  name?: string | null;
  action?: string;
  revision?: number;
  updated_by?: string;
  updated_by_name?: string | null;
  version_id?: string;
  label?: string | null;
  created_by?: string;
  from?: number;
  to?: number;
  empty?: boolean;
  [key: string]: unknown;
}

@Injectable({ providedIn: 'root' })
export class DocumentWsService {
  private readonly zone = inject(NgZone);
  private ws: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private documentId: string | null = null;
  private token: string | null = null;

  readonly connected = signal(false);
  readonly presenceUsers = signal<PresenceUser[]>([]);
  readonly lastUpdate = signal<{ revision: number; updated_by: string; updated_by_name: string | null } | null>(null);
  readonly lastVersion = signal<{ version_id: string; label: string | null; created_by: string } | null>(null);
  readonly remoteCursors = signal<Record<string, RemoteCursor>>({});

  connect(documentId: string, token: string): void {
    this.disconnect();
    this.documentId = documentId;
    this.token = token;
    this.openSocket();
  }

  private openSocket(): void {
    if (!this.documentId || !this.token) return;
    const wsUrl = environment.apiBaseUrl.replace(/^http/, 'ws') + `/ws/documents/${this.documentId}?token=${this.token}`;
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => this.zone.run(() => this.connected.set(true));
    this.ws.onclose = () => this.zone.run(() => {
      this.connected.set(false);
      this.scheduleReconnect();
    });
    this.ws.onerror = () => this.zone.run(() => {
      this.connected.set(false);
    });
    this.ws.onmessage = (event) => this.zone.run(() => this.handleMessage(event.data));
  }

  private handleMessage(raw: string): void {
    let msg: WsMessage;
    try {
      msg = JSON.parse(raw);
    } catch {
      return;
    }
    switch (msg.type) {
      case 'presence_list': {
        const seen = new Set<string>();
        const users = (msg.users ?? [])
          .filter((user) => {
            if (seen.has(user.user_id)) return false;
            seen.add(user.user_id);
            return true;
          })
          .map((user, index) => ({ ...user, color: PRESENCE_COLORS[index % PRESENCE_COLORS.length] }));
        this.presenceUsers.set(users);
        // Drop cursors for collaborators who left — otherwise their name tag
        // stays frozen in the document until another cursor message arrives.
        const presentIds = new Set(users.map((u) => u.user_id));
        this.remoteCursors.update((cursors) => {
          const next = { ...cursors };
          for (const uid of Object.keys(next)) {
            if (!presentIds.has(uid)) delete next[uid];
          }
          return next;
        });
        break;
      }
      case 'presence':
        // Individual join/leave; presence_list will follow with the full list
        break;
      case 'document_updated':
        this.lastUpdate.set({
          revision: msg.revision ?? 0,
          updated_by: msg.updated_by ?? '',
          updated_by_name: msg.updated_by_name ?? null,
        });
        break;
      case 'version_created':
        this.lastVersion.set({
          version_id: msg.version_id ?? '',
          label: msg.label ?? null,
          created_by: msg.created_by ?? '',
        });
        break;
      case 'cursor': {
        const cursor: RemoteCursor = {
          user_id: msg.user_id ?? '',
          name: msg.name ?? null,
          color: this.presenceUsers().find((u) => u.user_id === msg.user_id)?.color,
          from: msg.from ?? 0,
          to: msg.to ?? 0,
          empty: msg.empty ?? false,
        };
        this.remoteCursors.update((cursors) => {
          const updated = { ...cursors, [cursor.user_id]: cursor };
          // Remove cursors for users no longer present
          const presentIds = new Set(this.presenceUsers().map((u) => u.user_id));
          for (const uid of Object.keys(updated)) {
            if (!presentIds.has(uid)) delete updated[uid];
          }
          return updated;
        });
        break;
      }
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = setTimeout(() => {
      if (this.documentId && this.token) this.openSocket();
    }, 3000);
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.documentId = null;
    this.token = null;
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.close();
      this.ws = null;
    }
    this.connected.set(false);
    this.presenceUsers.set([]);
    this.lastUpdate.set(null);
    this.lastVersion.set(null);
    this.remoteCursors.set({});
  }

  sendCursor(from: number, to: number, empty: boolean): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
    this.ws.send(JSON.stringify({ type: 'cursor', from, to, empty }));
  }
}
