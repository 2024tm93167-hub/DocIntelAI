import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { DocumentStats, ExportFormat, ReadabilityResult, UserStats } from '../models/analytics.model';

@Injectable({
  providedIn: 'root',
})
export class AnalyticsService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = environment.apiBaseUrl;

  getUserStats(): Observable<UserStats> {
    return this.http.get<UserStats>(`${this.baseUrl}/analytics`);
  }

  getDocumentStats(documentId: string): Observable<DocumentStats> {
    return this.http.get<DocumentStats>(`${this.baseUrl}/documents/${documentId}/stats`);
  }

  evaluateDocument(documentId: string): Observable<ReadabilityResult> {
    return this.http.get<ReadabilityResult>(`${this.baseUrl}/documents/${documentId}/evaluate`);
  }

  exportDocument(documentId: string, format: ExportFormat): Observable<Blob> {
    return this.http.get(`${this.baseUrl}/documents/${documentId}/export`, {
      params: { format },
      responseType: 'blob',
    });
  }
}
