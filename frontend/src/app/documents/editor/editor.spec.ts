import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { MatDialogRef } from '@angular/material/dialog';
import { provideRouter } from '@angular/router';
import { Editor as TiptapEditor } from '@tiptap/core';
import { StarterKit } from '@tiptap/starter-kit';
import { of, Subject } from 'rxjs';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { Editor } from './editor';
import { AiService } from '../../core/services/ai.service';
import { NotificationService } from '../../core/services/notification.service';
import { Document } from '../../core/models/document.model';
import { VersionSummary } from '../../core/models/version.model';
import { environment } from '../../../environments/environment';

const ai = { rewrite: vi.fn(), generateStream: vi.fn(), summarize: vi.fn(), action: vi.fn() };
const savedDocument: Document = {
  id: 'doc', title: 'Current', owner_id: 'owner', content: { type: 'doc', content: [] },
  revision: 5, word_count: 0, updated_by: 'owner', created_at: null, updated_at: null,
};
const savedVersion: VersionSummary = {
  id: 'version', document_id: 'doc', title: 'Earlier', label: null, word_count: 2, created_at: null,
  created_by: 'owner', author_name: 'Owner', source: 'manual', document_revision: 1, restored_from_version_id: null,
};
const restoreUrl = `${environment.apiBaseUrl}/documents/doc/versions/version/restore`;

describe('Editor AI acceptance', () => {
  let component: Editor;
  let tiptap: TiptapEditor;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [Editor],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting(),
        { provide: AiService, useValue: ai },
        { provide: NotificationService, useValue: { success: vi.fn(), error: vi.fn(), info: vi.fn() } },
      ],
    });
    component = TestBed.createComponent(Editor).componentInstance;
    tiptap = new TiptapEditor({ extensions: [StarterKit], content: '<p>Hello world</p>' });
    component['editor'] = tiptap;
    ai.action.mockReturnValue(of({ output: 'Greetings' }));
    component.setAiMode('rewrite');
  });

  afterEach(() => {
    component.ngOnDestroy();
    TestBed.inject(HttpTestingController).verify();
    vi.restoreAllMocks();
  });

  it('applies to the original selection even when the cursor moves', () => {
    tiptap.commands.setTextSelection({ from: 1, to: 6 });
    component.runAi();
    tiptap.commands.setTextSelection(12);
    component.applyAiOutput();
    expect(tiptap.getText()).toContain('Greetings');
    expect(tiptap.getText()).toContain('world');
    expect(tiptap.getText()).not.toContain('Hello');
    const accepted = tiptap.getJSON();
    component.applyAiOutput();
    expect(tiptap.getJSON()).toEqual(accepted);
  });

  it('refuses to apply stale output after document edits', () => {
    component.runAi();
    tiptap.commands.insertContent('New edit');
    const current = tiptap.getJSON();
    component.applyAiOutput();
    expect(tiptap.getJSON()).toEqual(current);
    expect(component.aiError()).toContain('document changed');
  });

  it('inserts model HTML literally as text, not executable markup', () => {
    const text = '<img src=x onerror=alert(1)>';
    ai.action.mockReturnValue(of({ output: text }));
    component.runAi();
    component.applyAiOutput();
    expect(tiptap.getText()).toBe(text);
    expect(tiptap.getHTML()).toContain('&lt;img');
  });

  it('inserts markdown AI output as real headings and lists', () => {
    component.setAiMode('generate');
    component.aiPrompt.setValue('Write about soil');
    ai.action.mockReturnValue(of({ output: '# Soil\n\nIntro text.\n\n- clay\n- loam' }));
    component.runAi();
    component.insertAiOutput();
    const types = (tiptap.getJSON().content ?? []).map((n: { type: string }) => n.type);
    expect(types).toEqual(expect.arrayContaining(['paragraph', 'heading', 'bulletList']));
    const heading = (tiptap.getJSON().content ?? []).find((n: { type: string }) => n.type === 'heading');
    expect(heading?.attrs?.['level']).toBe(1);
  });

  it('cancels a rewrite when changing modes', () => {
    const response = new Subject<{ output: string }>();
    ai.action.mockReturnValue(response);
    component.runAi();
    component.setAiMode('generate');
    response.next({ output: 'Obsolete response' });
    expect(component.aiOutput()).toBe('');
    expect(component.aiLoading()).toBe(false);
  });

  it('supports keyboard resize within safe bounds', () => {
    component.resizePanelWithKeyboard(new KeyboardEvent('keydown', { key: 'Home' }));
    expect(component.sidePanelWidth()).toBe(260);
    component.resizePanelWithKeyboard(new KeyboardEvent('keydown', { key: 'ArrowLeft' }));
    expect(component.sidePanelWidth()).toBe(280);
    component.resizePanelWithKeyboard(new KeyboardEvent('keydown', { key: 'End' }));
    expect(component.sidePanelWidth()).toBe(component.panelMaxWidth());
  });

  it('handles pointer cancellation and restores existing body styles', () => {
    document.body.style.userSelect = 'text';
    component.startPanelResize(new PointerEvent('pointerdown', { button: 0, isPrimary: true, pointerId: 1, clientX: 600 }));
    expect(component.panelResizing()).toBe(true);
    document.dispatchEvent(new PointerEvent('pointercancel', { pointerId: 1 }));
    expect(component.panelResizing()).toBe(false);
    expect(document.body.style.userSelect).toBe('text');
    document.body.style.userSelect = '';
  });

  it('restores only after confirmation and uses the current revision', () => {
    component.autosave.initialize(savedDocument);
    vi.spyOn(component['dialog'], 'open').mockReturnValue({ afterClosed: () => of(true) } as MatDialogRef<unknown>);
    component.restoreVersion(savedVersion);
    const http = TestBed.inject(HttpTestingController);
    const request = http.expectOne(restoreUrl);
    expect(request.request.body).toEqual({ base_revision: 5 });
    expect(tiptap.isEditable).toBe(false);
    expect(component.titleControl.disabled).toBe(true);
    expect(component.confirmLeave()).toBe(false);
    const content = { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Earlier text' }] }] };
    request.flush({ ...savedDocument, title: 'Earlier', content, revision: 6 });
    http.expectOne(`${environment.apiBaseUrl}/documents/doc/versions`).flush([savedVersion]);
    expect(tiptap.getText()).toBe('Earlier text');
    expect(component.autosave.document()?.revision).toBe(6);
    expect(component.autosave.hasUnsavedChanges()).toBe(false);
    expect(tiptap.isEditable).toBe(true);
    expect(component.titleControl.enabled).toBe(true);
  });

  it('preserves local content on restore conflict', () => {
    component.autosave.initialize(savedDocument);
    const before = tiptap.getJSON();
    vi.spyOn(component['dialog'], 'open').mockReturnValue({ afterClosed: () => of(true) } as MatDialogRef<unknown>);
    component.restoreVersion(savedVersion);
    TestBed.inject(HttpTestingController).expectOne(restoreUrl).flush({}, { status: 409, statusText: 'Conflict' });
    expect(tiptap.getJSON()).toEqual(before);
    expect(component.autosave.document()?.revision).toBe(5);
    expect(component.versionError()).toContain('changed elsewhere');
    expect(tiptap.isEditable).toBe(true);
  });

  it('does not restore if edits become pending while confirming', () => {
    component.autosave.initialize(savedDocument);
    const decision = new Subject<boolean>();
    vi.spyOn(component['dialog'], 'open').mockReturnValue({ afterClosed: () => decision.asObservable() } as MatDialogRef<unknown>);
    component.restoreVersion(savedVersion);
    component.autosave.queue({ title: 'Unsaved', content: tiptap.getJSON() });
    decision.next(true);
    TestBed.inject(HttpTestingController).expectNone(restoreUrl);
    expect(component.restoringVersion()).toBe(false);
  });

  it('does not restore when confirmation is cancelled', () => {
    component.autosave.initialize(savedDocument);
    vi.spyOn(component['dialog'], 'open').mockReturnValue({ afterClosed: () => of(false) } as MatDialogRef<unknown>);
    component.restoreVersion(savedVersion);
    TestBed.inject(HttpTestingController).expectNone(restoreUrl);
    expect(component.restoringVersion()).toBe(false);
  });

  it('keeps resize functional when storage is unavailable', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('Storage unavailable'); });
    expect(() => component.resizePanelWithKeyboard(new KeyboardEvent('keydown', { key: 'Home' }))).not.toThrow();
    expect(component.sidePanelWidth()).toBe(260);
  });
});
