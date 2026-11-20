import { inject } from '@angular/core';
import { type CanActivateFn, Router } from '@angular/router';

import { type Role, Session, homeFor } from './session';

export const authGuard: CanActivateFn = (_route, state) => {
  const session = inject(Session);
  return session.isAuthenticated()
    ? true
    : inject(Router).createUrlTree(['/connexion'], { queryParams: { suite: state.url } });
};

export const guestGuard: CanActivateFn = () => {
  const session = inject(Session);
  return session.isAuthenticated() ? inject(Router).parseUrl(homeFor(session)) : true;
};

/** Route data `roles`: any of them grants access (a user can hold several roles). */
export const roleGuard: CanActivateFn = (route) => {
  const session = inject(Session);
  const roles = (route.data['roles'] ?? []) as Role[];
  if (roles.length === 0 || session.hasRole(...roles)) return true;
  return inject(Router).parseUrl(homeFor(session));
};

export const superadminGuard: CanActivateFn = () => {
  const session = inject(Session);
  return session.isSuperadmin() ? true : inject(Router).parseUrl(homeFor(session));
};
