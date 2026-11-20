import type { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';

import { KioskSession } from './kiosk-session';

/** Machine calls (/api/v1/kiosk/) carry the tablet's token and company code. */
export const kioskInterceptor: HttpInterceptorFn = (req, next) => {
  if (!req.url.startsWith('/api/v1/kiosk/')) return next(req);
  const session = inject(KioskSession);
  const headers = session.headers();
  if (!headers['X-Company-Code'] && session.pairingCompanyCode) {
    headers['X-Company-Code'] = session.pairingCompanyCode;
  }
  return next(req.clone({ setHeaders: headers }));
};
