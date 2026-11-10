import { TestBed } from '@angular/core/testing';
import { HttpEventType, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AiService } from './ai.service';
import { environment } from '../../../environments/environment';

const url = `${environment.apiBaseUrl}/ai/generate`;
const delta = (text: string) => JSON.stringify({ type: 'delta', text }) + '\n';
const done = '{"type":"done"}\n';

describe('AiService streaming', () => {
  let service: AiService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(AiService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('parses split frames, preserves Unicode and does not duplicate cumulative progress', () => {
    const output: string[] = [];
    const complete = vi.fn();
    service.generateStream('Write').subscribe({ next: (text) => output.push(text), complete });
    const request = http.expectOne(url);
    expect(request.request.headers.get('Accept')).toBe('application/x-ndjson');
    const first = delta('వ్యవసాయం\n');
    request.event({ type: HttpEventType.DownloadProgress, loaded: 6, partialText: first.slice(0, 6) });
    expect(output).toEqual([]);
    request.event({ type: HttpEventType.DownloadProgress, loaded: first.length, partialText: first });
    request.flush(first + delta('Hello') + done);
    expect(output).toEqual(['వ్యవసాయం\n', 'వ్యవసాయం\nHello']);
    expect(complete).toHaveBeenCalledOnce();
  });

  it('reads a complete response even when progress events are absent', () => {
    const output = vi.fn();
    service.generate('Write').subscribe(output);
    http.expectOne(url).flush(delta('Final text') + done);
    expect(output).toHaveBeenCalledWith({ output: 'Final text' });
  });

  it.each([
    delta('Partial'),
    delta('Partial') + '{"type":"error","message":"private error"}\n',
    '{invalid json}\n',
    done,
  ])('rejects incomplete or failed streams instead of reporting success', (body) => {
    const error = vi.fn();
    const complete = vi.fn();
    service.generateStream('Write').subscribe({ error, complete });
    http.expectOne(url).flush(body);
    expect(error).toHaveBeenCalledOnce();
    expect(complete).not.toHaveBeenCalled();
  });

  it('aborts the HTTP request on unsubscribe', () => {
    const subscription = service.generateStream('Write').subscribe();
    const request = http.expectOne(url);
    subscription.unsubscribe();
    expect(request.cancelled).toBe(true);
  });
});
