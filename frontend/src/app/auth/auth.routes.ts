import { Routes } from '@angular/router';

export const AUTH_ROUTES: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'login' },
  { path: 'login', loadComponent: () => import('./login/login').then((m) => m.Login) },
  { path: 'register', loadComponent: () => import('./register/register').then((m) => m.Register) },
];
