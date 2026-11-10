import { TestBed } from '@angular/core/testing';
import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { firstValueFrom } from 'rxjs';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { authInterceptor } from './auth.interceptor';
import { AuthService } from '../services/auth.service';
import { environment } from '../../../environments/environment';

describe('authInterceptor', () => {
  let http: HttpClient;
  let requests: HttpTestingController;
  const auth = { getIdToken: vi.fn().mockResolvedValue('test-token') };

  beforeEach(() => {
    auth.getIdToken.mockClear();
    TestBed.configureTestingModule({ providers: [
      provideHttpClient(withInterceptors([authInterceptor])), provideHttpClientTesting(),
      { provide: AuthService, useValue: auth },
    ] });
    http = TestBed.inject(HttpClient);
    requests = TestBed.inject(HttpTestingController);
  });

  afterEach(() => requests.verify());

  it('attaches token only to backend requests', async () => {
    const url = `${environment.apiBaseUrl}/documents`;
    const result = firstValueFrom(http.get(url));
    await Promise.resolve();
    const request = requests.expectOne(url);
    expect(request.request.headers.get('Authorization')).toBe('Bearer test-token');
    request.flush([]);
    await result;
  });

  it('does not leak a token to a URL containing the backend as userinfo', async () => {
    const url = `${environment.apiBaseUrl}@external.example/documents`;
    const result = firstValueFrom(http.get(url));
    await Promise.resolve();
    const request = requests.expectOne(url);
    expect(request.request.headers.has('Authorization')).toBe(false);
    expect(auth.getIdToken).not.toHaveBeenCalled();
    request.flush([]);
    await result;
  });
});
