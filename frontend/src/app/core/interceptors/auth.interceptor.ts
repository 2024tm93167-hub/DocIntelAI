import { DOCUMENT } from '@angular/common';
import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { from, switchMap } from 'rxjs';

import { environment } from '../../../environments/environment';
import { AuthService } from '../services/auth.service';

/** Attaches the current Firebase ID token to every request sent to the DocIntel AI backend. */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const apiUrl = new URL(environment.apiBaseUrl);
  const requestUrl = new URL(req.url, inject(DOCUMENT).baseURI);
  const apiPath = apiUrl.pathname.replace(/\/$/, '');
  if (requestUrl.origin !== apiUrl.origin ||
      (requestUrl.pathname !== apiPath && !requestUrl.pathname.startsWith(`${apiPath}/`))) {
    return next(req);
  }

  const auth = inject(AuthService);

  return from(auth.getIdToken()).pipe(
    switchMap((token) => {
      const authorizedReq = token
        ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
        : req;
      return next(authorizedReq);
    })
  );
};
