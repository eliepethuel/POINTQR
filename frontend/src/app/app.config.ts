import { provideHttpClient, withFetch, withInterceptors } from '@angular/common/http';
import {
  type ApplicationConfig,
  inject,
  provideAppInitializer,
  provideBrowserGlobalErrorListeners,
} from '@angular/core';
import {
  provideRouter,
  withComponentInputBinding,
  withInMemoryScrolling,
  withViewTransitions,
} from '@angular/router';

import { provideApiConfiguration } from './api/api-configuration';
import { routes } from './app.routes';
import { authInterceptor } from './core/auth/auth-interceptor';
import { Session } from './core/auth/session';
import { ThemeService } from './core/theme/theme';
import { MotionService } from './shared/motion/motion-service';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideHttpClient(withFetch(), withInterceptors([authInterceptor])),
    // Same-origin API: proxied by the dev server, by the reverse proxy in production.
    provideApiConfiguration(''),
    provideRouter(
      routes,
      withComponentInputBinding(),
      withViewTransitions({
        skipInitialTransition: true,
        // Reduced motion: plain navigation, no cross-fade between pages.
        onViewTransitionCreated: ({ transition }) => {
          if (inject(MotionService).reduced()) transition.skipTransition();
        },
      }),
      withInMemoryScrolling({ scrollPositionRestoration: 'enabled', anchorScrolling: 'enabled' }),
    ),
    // Restore the session from the HttpOnly refresh cookie before the first navigation.
    provideAppInitializer(() => {
      inject(ThemeService);
      return inject(Session).restore();
    }),
  ],
};
