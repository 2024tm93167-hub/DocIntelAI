import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpEventType } from '@angular/common/http';
import { Observable } from 'rxjs';
import { distinctUntilChanged, last, map } from 'rxjs/operators';

import { environment } from '../../../environments/environment';
import { AiActionInfo, AiActionRequest, AiGenerateRequest, AiResponse, AiRewriteRequest, AiSummarizeRequest } from '../models/ai.model';

@Injectable({
  providedIn: 'root',
})
export class AiService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = environment.apiBaseUrl;

  rewrite(text: string, instruction?: string): Observable<AiResponse> {
    const body: AiRewriteRequest = { text, instruction };
    return this.http.post<AiResponse>(`${this.baseUrl}/ai/rewrite`, body);
  }

  summarize(text: string, maxWords = 100): Observable<AiResponse> {
    const body: AiSummarizeRequest = { text, max_words: maxWords };
    return this.http.post<AiResponse>(`${this.baseUrl}/ai/summarize`, body);
  }

  /** Runs a named AI writing action (grammar, tone, continue, outline, custom, etc.). */
  action(request: AiActionRequest): Observable<AiResponse> {
    return this.http.post<AiResponse>(`${this.baseUrl}/ai/action`, request);
  }

  suggestTitles(text: string): Observable<{ titles: string[] }> {
    return this.http.post<{ titles: string[] }>(`${this.baseUrl}/ai/titles`, { text });
  }

  listActions(): Observable<AiActionInfo[]> {
    return this.http.get<AiActionInfo[]>(`${this.baseUrl}/ai/actions`);
  }

  generate(prompt: string): Observable<AiResponse> {
    return this.generateStream(prompt).pipe(last(), map((output) => ({ output })));
  }

  /** Streams the generated text; emits the accumulated output as chunks arrive. */
  generateStream(prompt: string): Observable<string> {
    const body: AiGenerateRequest = { prompt };
    return new Observable<string>((subscriber) => {
      let consumed = 0;
      let buffer = '';
      let output = '';
      let done = false;
      const request = this.http.post(`${this.baseUrl}/ai/generate`, body, {
        observe: 'events', responseType: 'text', reportProgress: true,
        headers: { Accept: 'application/x-ndjson' },
      }).subscribe({
        next: (event) => {
          const text = event.type === HttpEventType.DownloadProgress ? event.partialText
            : event.type === HttpEventType.Response ? event.body : null;
          if (text == null) return;
          try {
            buffer += text.slice(consumed);
            consumed = text.length;
            let newline: number;
            while ((newline = buffer.indexOf('\n')) >= 0) {
              const line = buffer.slice(0, newline).trim();
              buffer = buffer.slice(newline + 1);
              if (!line) continue;
              const message: { type?: string; text?: unknown } = JSON.parse(line);
              if (done) throw new Error('Unexpected content after generation completed.');
              if (message.type === 'error') throw new Error('Generation was interrupted. Please retry.');
              if (message.type === 'done') {
                done = true;
              } else if (message.type === 'delta' && typeof message.text === 'string') {
                output += message.text;
                subscriber.next(output);
              } else {
                throw new Error('The AI provider returned an invalid response.');
              }
            }
          } catch (error) {
            subscriber.error(error);
          }
        },
        error: (error) => subscriber.error(error),
        complete: () => {
          if (!done || buffer.trim() || !output.trim()) {
            subscriber.error(new Error('Generation did not finish. Please retry.'));
          } else {
            subscriber.complete();
          }
        },
      });
      return () => request.unsubscribe();
    }).pipe(distinctUntilChanged());
  }
}
