import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import { SharingService } from './sharing.service';
import { environment } from '../../../environments/environment';

const docId = 'doc-1';
const base = `${environment.apiBaseUrl}/documents/${docId}/collaborators`;

describe('SharingService', () => {
  let service: SharingService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(SharingService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('lists collaborators', () => {
    service.list(docId).subscribe();
    const req = http.expectOne(base);
    expect(req.request.method).toBe('GET');
    req.flush([]);
  });

  it('invites a collaborator', () => {
    service.invite(docId, { email: 'new@example.com', role: 'editor' }).subscribe();
    const req = http.expectOne(base);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ email: 'new@example.com', role: 'editor' });
    req.flush({ id: 'c1', document_id: docId, user_id: 'u1', role: 'editor', email: 'new@example.com', name: null, created_at: null, created_by: null });
  });

  it('removes a collaborator', () => {
    service.remove(docId, 'c1').subscribe();
    const req = http.expectOne(`${base}/c1`);
    expect(req.request.method).toBe('DELETE');
    req.flush(null);
  });
});
