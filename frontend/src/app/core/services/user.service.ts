import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { AppUser } from '../models/user.model';

/** Talks to the FastAPI backend for the authenticated user's own profile. */
@Injectable({ providedIn: 'root' })
export class UserService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiBaseUrl}/users`;

  /** Fetches (and auto-provisions on the backend) the current user's profile. */
  getMe(): Observable<AppUser> {
    return this.http.get<AppUser>(`${this.baseUrl}/me`);
  }
}
