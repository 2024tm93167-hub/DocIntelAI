import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { Document } from '../models/document.model';
import { environment } from '../../../environments/environment';
import { Suggestion, SuggestionCreate, SuggestionStatus, SuggestionUpdate } from '../models/suggestion.model';

@Injectable({ providedIn: 'root' })
export class SuggestionService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = environment.apiBaseUrl;

  private url(documentId: string): string {
    return `${this.baseUrl}/documents/${documentId}/suggestions`;
  }

  list(documentId: string, status?: SuggestionStatus): Observable<Suggestion[]> {
    const params = status ? { status } : undefined;
    return this.http.get<Suggestion[]>(this.url(documentId), { params });
  }

  analyze(documentId: string, revision: number, text?: string): Observable<Suggestion[]> {
    return this.http.post<Suggestion[]>(`${this.url(documentId)}/analyze`, {
      base_revision: revision,
      ...(text ? { text } : {}),
    });
  }

  apply(documentId: string, suggestionId: string, revision: number): Observable<{ document: Document; suggestion: Suggestion }> {
    return this.http.post<{ document: Document; suggestion: Suggestion }>(`${this.url(documentId)}/${suggestionId}/apply`, { base_revision: revision });
  }

  create(documentId: string, body: SuggestionCreate): Observable<Suggestion> {
    return this.http.post<Suggestion>(this.url(documentId), body);
  }

  update(documentId: string, suggestionId: string, body: SuggestionUpdate): Observable<Suggestion> {
    return this.http.patch<Suggestion>(`${this.url(documentId)}/${suggestionId}`, body);
  }

  delete(documentId: string, suggestionId: string): Observable<void> {
    return this.http.delete<void>(`${this.url(documentId)}/${suggestionId}`);
  }
}
