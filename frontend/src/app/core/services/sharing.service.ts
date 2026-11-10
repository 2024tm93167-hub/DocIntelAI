import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { Collaborator, CollaboratorInvite } from '../models/collaborator.model';

@Injectable({ providedIn: 'root' })
export class SharingService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = environment.apiBaseUrl;

  private url(documentId: string): string {
    return `${this.baseUrl}/documents/${documentId}/collaborators`;
  }

  list(documentId: string): Observable<Collaborator[]> {
    return this.http.get<Collaborator[]>(this.url(documentId));
  }

  invite(documentId: string, body: CollaboratorInvite): Observable<Collaborator> {
    return this.http.post<Collaborator>(this.url(documentId), body);
  }

  remove(documentId: string, collaboratorId: string): Observable<void> {
    return this.http.delete<void>(`${this.url(documentId)}/${collaboratorId}`);
  }
}
