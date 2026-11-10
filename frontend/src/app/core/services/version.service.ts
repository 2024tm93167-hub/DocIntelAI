import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { DiffOut, VersionOut, VersionSummary } from '../models/version.model';
import { Document } from '../models/document.model';

@Injectable({
  providedIn: 'root',
})
export class VersionService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = environment.apiBaseUrl;

  private url(documentId: string, versionId?: string): string {
    const path = versionId ? `documents/${documentId}/versions/${versionId}` : `documents/${documentId}/versions`;
    return `${this.baseUrl}/${path}`;
  }

  create(documentId: string, label?: string | null): Observable<VersionOut> {
    return this.http.post<VersionOut>(this.url(documentId), { label });
  }

  list(documentId: string): Observable<VersionSummary[]> {
    return this.http.get<VersionSummary[]>(this.url(documentId));
  }

  get(documentId: string, versionId: string): Observable<VersionOut> {
    return this.http.get<VersionOut>(this.url(documentId, versionId));
  }

  delete(documentId: string, versionId: string): Observable<void> {
    return this.http.delete<void>(this.url(documentId, versionId));
  }

  restore(documentId: string, versionId: string, baseRevision: number): Observable<Document> {
    return this.http.post<Document>(`${this.url(documentId, versionId)}/restore`, { base_revision: baseRevision });
  }

  diff(documentId: string, versionId: string, compareTo?: string | null): Observable<DiffOut> {
    const params: Record<string, string> = {};
    if (compareTo) {
      params['compare_to'] = compareTo;
    }
    return this.http.get<DiffOut>(`${this.url(documentId, versionId)}/diff`, { params });
  }
}
