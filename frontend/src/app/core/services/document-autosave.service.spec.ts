import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { DocumentAutosaveService } from './document-autosave.service';
import { Document, DocumentDraft } from '../models/document.model';
import { environment } from '../../../environments/environment';

const document: Document = {
  id: 'doc-1', owner_id: 'owner', title: 'Original', revision: 0, updated_by: null,
  content: { type: 'doc', content: [] }, word_count: 0, created_at: null, updated_at: null,
};
const url = `${environment.apiBaseUrl}/documents/doc-1`;
const draft = (title: string): DocumentDraft => ({ title, content: document.content });

describe('DocumentAutosaveService', () => {
  let service: DocumentAutosaveService;
  let http: HttpTestingController;

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting(), DocumentAutosaveService],
    });
    service = TestBed.inject(DocumentAutosaveService);
    http = TestBed.inject(HttpTestingController);
    service.initialize(document);
  });

  afterEach(() => {
    service.ngOnDestroy();
    http.verify();
    vi.useRealTimers();
  });

  it('marks dirty immediately and debounces keystrokes', () => {
    service.queue(draft('First'));
    expect(service.hasUnsavedChanges()).toBe(true);
    expect(service.status()).toBe('unsaved');
    vi.advanceTimersByTime(600);
    service.queue(draft('Second'));
    vi.advanceTimersByTime(1199);
    http.expectNone(url);
    vi.advanceTimersByTime(1);
    const request = http.expectOne(url);
    expect(request.request.body).toEqual({ ...draft('Second'), base_revision: 0 });
    request.flush({ ...document, title: 'Second', revision: 1 });
    expect(service.status()).toBe('saved');
  });

  it('serializes writes and coalesces edits using the acknowledged revision', () => {
    service.queue(draft('First'));
    service.flush();
    const first = http.expectOne(url);
    service.queue(draft('Second'));
    service.queue(draft('Latest'));
    vi.advanceTimersByTime(2000);
    http.expectNone(url);
    first.flush({ ...document, title: 'First', revision: 1 });
    expect(service.status()).toBe('saving');
    const second = http.expectOne(url);
    expect(second.request.body).toEqual({ ...draft('Latest'), base_revision: 1 });
    second.flush({ ...document, title: 'Latest', revision: 2 });
    expect(service.document()?.revision).toBe(2);
    expect(service.hasUnsavedChanges()).toBe(false);
  });

  it('retains the latest draft and allows retry after a network error', () => {
    service.queue(draft('First'));
    service.flush();
    const request = http.expectOne(url);
    service.queue(draft('Latest'));
    request.flush({}, { status: 503, statusText: 'Unavailable' });
    vi.advanceTimersByTime(2000);
    http.expectNone(url);
    expect(service.status()).toBe('error');
    service.retry();
    const retry = http.expectOne(url);
    expect(retry.request.body.title).toBe('Latest');
    retry.flush({ ...document, title: 'Latest', revision: 1 });
    expect(service.status()).toBe('saved');
  });

  it('pauses on a conflict without resending or force overwriting', () => {
    service.queue(draft('Local draft'));
    service.flush();
    http.expectOne(url).flush({}, { status: 409, statusText: 'Conflict' });
    service.queue(draft('Still local'));
    service.retry();
    service.flush();
    vi.advanceTimersByTime(2000);
    http.expectNone(url);
    expect(service.status()).toBe('conflict');
    expect(service.document()?.revision).toBe(0);
    expect(service.hasUnsavedChanges()).toBe(true);
  });

  it('does not send invalid titles and keeps unsaved state', () => {
    service.queue(draft(''));
    service.flush();
    http.expectNone(url);
    expect(service.status()).toBe('error');
    service.queue(draft('Valid'));
    service.retry();
    http.expectOne(url).flush({ ...document, title: 'Valid', revision: 1 });
    expect(service.status()).toBe('saved');
  });

  it('cancels pending debounce on destruction', () => {
    service.queue(draft('Pending'));
    service.ngOnDestroy();
    vi.advanceTimersByTime(2000);
    http.expectNone(url);
  });

  it('cancels active requests on destruction', () => {
    service.queue(draft('Pending'));
    service.flush();
    const request = http.expectOne(url);
    service.ngOnDestroy();
    expect(request.cancelled).toBe(true);
  });
});
