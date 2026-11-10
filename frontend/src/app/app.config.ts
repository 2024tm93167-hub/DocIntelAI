import { provideHttpClient, withFetch, withInterceptors } from '@angular/common/http';
import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { NavigationError, provideRouter, withNavigationErrorHandler } from '@angular/router';

import { authInterceptor } from './core/interceptors/auth.interceptor';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideRouter(
      routes,
      withNavigationErrorHandler((e: NavigationError) => {
        const message = String(e.error?.message ?? e.error ?? '');
        if (e.url && /chunk|import|module|fetch/i.test(message)) {
          location.assign(e.url);
        }
      }),
    ),
    provideAnimationsAsync(),
    provideHttpClient(withInterceptors([authInterceptor]), withFetch()),
  ]
};
