import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { SuggestionService } from './suggestion.service';
import { environment } from '../../../environments/environment';

const docId = 'doc-1';
const base = `${environment.apiBaseUrl}/documents/${docId}/suggestions`;

describe('SuggestionService', () => {
  let service: SuggestionService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(SuggestionService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('lists suggestions with an optional status filter', () => {
    service.list(docId, 'pending').subscribe();
    const req = http.expectOne(`${base}?status=pending`);
    expect(req.request.method).toBe('GET');
    req.flush([]);
  });

  it('lists suggestions without a status filter', () => {
    service.list(docId).subscribe();
    const req = http.expectOne(base);
    expect(req.request.method).toBe('GET');
    req.flush([]);
  });

  it('creates a suggestion', () => {
    service.create(docId, { type: 'grammar', original_text: 'hi', suggested_text: 'Hi' }).subscribe();
    const req = http.expectOne(base);
    expect(req.request.method).toBe('POST');
    expect(req.request.body.type).toBe('grammar');
    req.flush({ id: 's1', document_id: docId, user_id: 'u1', type: 'grammar', original_text: 'hi', suggested_text: 'Hi', reason: null, status: 'pending', document_revision: 0, created_at: null, resolved_at: null, resolved_by: null });
  });

  it('updates a suggestion status with base_revision for accept', () => {
    service.update(docId, 's1', { status: 'accepted', base_revision: 3 }).subscribe();
    const req = http.expectOne(`${base}/s1`);
    expect(req.request.method).toBe('PATCH');
    expect(req.request.body).toEqual({ status: 'accepted', base_revision: 3 });
    req.flush({ id: 's1', document_id: docId, user_id: 'u1', type: 'grammar', original_text: 'hi', suggested_text: 'Hi', reason: null, status: 'accepted', document_revision: 3, created_at: null, resolved_at: null, resolved_by: 'u1' });
  });

  it('deletes a suggestion', () => {
    service.delete(docId, 's1').subscribe();
    const req = http.expectOne(`${base}/s1`);
    expect(req.request.method).toBe('DELETE');
    req.flush(null);
  });
});
