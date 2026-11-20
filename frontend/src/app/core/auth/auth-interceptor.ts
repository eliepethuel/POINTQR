import { HttpErrorResponse, type HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, from, switchMap, throwError } from 'rxjs';

import { Session } from './session';

const AUTH_PATHS = ['/api/v1/auth/login/', '/api/v1/auth/mfa/verify/', '/api/v1/auth/refresh/'];

/** Adds the in-memory access token and refreshes it silently once on a 401. */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const session = inject(Session);
  // Kiosk machine calls carry their own credentials (kiosk interceptor).
  if (req.url.startsWith('/api/v1/kiosk/')) return next(req);
  const isAuthCall = AUTH_PATHS.some((p) => req.url.startsWith(p));
  const withToken = () => {
    const token = session.token();
    return token && !isAuthCall
      ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
      : req;
  };

  return next(withToken()).pipe(
    catchError((error: unknown) => {
      if (!(error instanceof HttpErrorResponse) || error.status !== 401 || isAuthCall) {
        return throwError(() => error);
      }
      return from(session.refresh()).pipe(
        switchMap((ok) => (ok ? next(withToken()) : throwError(() => error))),
      );
    }),
  );
};
