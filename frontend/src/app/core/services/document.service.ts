import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { Document, DocumentSummary, DocumentUpdate } from '../models/document.model';

@Injectable({ providedIn: 'root' })
export class DocumentService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiBaseUrl}/documents`;

  list(): Observable<DocumentSummary[]> {
    return this.http.get<DocumentSummary[]>(this.baseUrl);
  }

  create(title = 'Untitled Document'): Observable<Document> {
    return this.http.post<Document>(this.baseUrl, { title });
  }

  get(id: string): Observable<Document> {
    return this.http.get<Document>(`${this.baseUrl}/${id}`);
  }

  update(id: string, changes: DocumentUpdate): Observable<Document> {
    return this.http.patch<Document>(`${this.baseUrl}/${id}`, changes);
  }

  delete(id: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/${id}`);
  }
}
