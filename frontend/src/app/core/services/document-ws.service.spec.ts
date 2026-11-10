import { TestBed } from '@angular/core/testing';
import { beforeEach, describe, expect, it, vi, afterEach } from 'vitest';

import { DocumentWsService, PRESENCE_COLORS } from './document-ws.service';

class MockWebSocket {
  static OPEN = 1;
  static CONNECTING = 0;
  static CLOSING = 2;
  static CLOSED = 3;
  onopen: ((ev: Event) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  close = vi.fn();
  static lastInstance: MockWebSocket | null = null;

  constructor() {
    MockWebSocket.lastInstance = this;
  }
}

describe('DocumentWsService', () => {
  let service: DocumentWsService;
  let ws: MockWebSocket;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(DocumentWsService);
    MockWebSocket.lastInstance = null;
    vi.stubGlobal('WebSocket', MockWebSocket);
  });

  afterEach(() => {
    service.disconnect();
    vi.unstubAllGlobals();
  });

  it('connects and sets connected on open', () => {
    service.connect('doc-1', 'token');
    ws = MockWebSocket.lastInstance!;
    expect(ws).toBeTruthy();
    ws.onopen!(new Event('open'));
    expect(service.connected()).toBe(true);
  });

  it('parses presence_list messages', () => {
    service.connect('doc-1', 'token');
    ws = MockWebSocket.lastInstance!;
    ws.onopen!(new Event('open'));
    ws.onmessage!(new MessageEvent('message', { data: JSON.stringify({ type: 'presence_list', users: [{ user_id: 'u1', name: 'Alice', email: 'a@e.com' }] }) }));
    expect(service.presenceUsers().length).toBe(1);
    expect(service.presenceUsers()[0].name).toBe('Alice');
  });

  it('parses document_updated messages', () => {
    service.connect('doc-1', 'token');
    ws = MockWebSocket.lastInstance!;
    ws.onopen!(new Event('open'));
    ws.onmessage!(new MessageEvent('message', { data: JSON.stringify({ type: 'document_updated', revision: 5, updated_by: 'u2', updated_by_name: 'Editor' }) }));
    expect(service.lastUpdate()?.revision).toBe(5);
    expect(service.lastUpdate()?.updated_by_name).toBe('Editor');
  });

  it('parses version_created messages', () => {
    service.connect('doc-1', 'token');
    ws = MockWebSocket.lastInstance!;
    ws.onopen!(new Event('open'));
    ws.onmessage!(new MessageEvent('message', { data: JSON.stringify({ type: 'version_created', version_id: 'v1', label: 'Draft', created_by: 'u2' }) }));
    expect(service.lastVersion()?.version_id).toBe('v1');
    expect(service.lastVersion()?.label).toBe('Draft');
  });

  it('disconnects and clears signals', () => {
    service.connect('doc-1', 'token');
    ws = MockWebSocket.lastInstance!;
    ws.onopen!(new Event('open'));
    ws.onmessage!(new MessageEvent('message', { data: JSON.stringify({ type: 'presence_list', users: [{ user_id: 'u1', name: 'Alice', email: null }] }) }));
    service.disconnect();
    expect(service.connected()).toBe(false);
    expect(service.presenceUsers().length).toBe(0);
    expect(ws.close).toHaveBeenCalled();
  });

  it('ignores invalid JSON', () => {
    service.connect('doc-1', 'token');
    ws = MockWebSocket.lastInstance!;
    ws.onopen!(new Event('open'));
    ws.onmessage!(new MessageEvent('message', { data: 'not json' }));
    expect(service.presenceUsers().length).toBe(0);
  });

  it('parses cursor messages and stores remote cursors', () => {
    service.connect('doc-1', 'token');
    ws = MockWebSocket.lastInstance!;
    ws.onopen!(new Event('open'));
    // Set presence first so cursor is retained
    ws.onmessage!(new MessageEvent('message', { data: JSON.stringify({ type: 'presence_list', users: [{ user_id: 'u2', name: 'Bob', email: 'b@e.com' }] }) }));
    ws.onmessage!(new MessageEvent('message', { data: JSON.stringify({ type: 'cursor', user_id: 'u2', name: 'Bob', from: 5, to: 10, empty: false }) }));
    const cursors = service.remoteCursors();
    expect(cursors['u2']).toBeTruthy();
    expect(cursors['u2'].from).toBe(5);
    expect(cursors['u2'].to).toBe(10);
    expect(cursors['u2'].name).toBe('Bob');
  });

  it('assigns a distinct color per user from presence order', () => {
    service.connect('doc-1', 'token');
    ws = MockWebSocket.lastInstance!;
    ws.onopen!(new Event('open'));
    ws.onmessage!(new MessageEvent('message', {
      data: JSON.stringify({
        type: 'presence_list',
        users: [
          { user_id: 'u1', name: 'Alice', email: 'a@e.com' },
          { user_id: 'u2', name: 'Bob', email: 'b@e.com' },
        ],
      }),
    }));
    const users = service.presenceUsers();
    expect(users[0].color).toBe(PRESENCE_COLORS[0]);
    expect(users[1].color).toBe(PRESENCE_COLORS[1]);
    expect(users[0].color).not.toBe(users[1].color);

    // Cursor messages pick up the user's assigned colour
    ws.onmessage!(new MessageEvent('message', { data: JSON.stringify({ type: 'cursor', user_id: 'u2', name: 'Bob', from: 1, to: 2, empty: false }) }));
    expect(service.remoteCursors()['u2'].color).toBe(PRESENCE_COLORS[1]);
  });

  it('removes cursors for users no longer present', () => {
    service.connect('doc-1', 'token');
    ws = MockWebSocket.lastInstance!;
    ws.onopen!(new Event('open'));
    ws.onmessage!(new MessageEvent('message', { data: JSON.stringify({ type: 'presence_list', users: [{ user_id: 'u2', name: 'Bob', email: 'b@e.com' }, { user_id: 'u3', name: 'Carol', email: 'c@e.com' }] }) }));
    ws.onmessage!(new MessageEvent('message', { data: JSON.stringify({ type: 'cursor', user_id: 'u2', name: 'Bob', from: 0, to: 5, empty: false }) }));
    ws.onmessage!(new MessageEvent('message', { data: JSON.stringify({ type: 'cursor', user_id: 'u3', name: 'Carol', from: 10, to: 15, empty: false }) }));
    expect(Object.keys(service.remoteCursors()).length).toBe(2);
    // Now u2 leaves
    ws.onmessage!(new MessageEvent('message', { data: JSON.stringify({ type: 'presence_list', users: [{ user_id: 'u3', name: 'Carol', email: 'c@e.com' }] }) }));
    ws.onmessage!(new MessageEvent('message', { data: JSON.stringify({ type: 'cursor', user_id: 'u3', name: 'Carol', from: 12, to: 18, empty: false }) }));
    const cursors = service.remoteCursors();
    expect(cursors['u2']).toBeUndefined();
    expect(cursors['u3']).toBeTruthy();
  });

  it('sends cursor updates via sendCursor', () => {
    service.connect('doc-1', 'token');
    ws = MockWebSocket.lastInstance!;
    ws.onopen!(new Event('open'));
    // Mock the send method
    (ws as any).send = vi.fn();
    (ws as any).readyState = 1; // OPEN
    service.sendCursor(3, 7, false);
    expect((ws as any).send).toHaveBeenCalledWith(JSON.stringify({ type: 'cursor', from: 3, to: 7, empty: false }));
  });

  it('does not send cursor when socket is not open', () => {
    service.connect('doc-1', 'token');
    ws = MockWebSocket.lastInstance!;
    ws.onopen!(new Event('open'));
    (ws as any).send = vi.fn();
    (ws as any).readyState = 0; // CONNECTING
    service.sendCursor(3, 7, false);
    expect((ws as any).send).not.toHaveBeenCalled();
  });

  it('clears remote cursors on disconnect', () => {
    service.connect('doc-1', 'token');
    ws = MockWebSocket.lastInstance!;
    ws.onopen!(new Event('open'));
    ws.onmessage!(new MessageEvent('message', { data: JSON.stringify({ type: 'presence_list', users: [{ user_id: 'u2', name: 'Bob', email: null }] }) }));
    ws.onmessage!(new MessageEvent('message', { data: JSON.stringify({ type: 'cursor', user_id: 'u2', name: 'Bob', from: 0, to: 5, empty: false }) }));
    expect(Object.keys(service.remoteCursors()).length).toBe(1);
    service.disconnect();
    expect(Object.keys(service.remoteCursors()).length).toBe(0);
  });
});
