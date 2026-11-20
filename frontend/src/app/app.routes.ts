import type { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    title: 'PointQR — Le pointage qui ne ment pas.',
    loadComponent: () => import('./features/landing/hello-page').then((m) => m.HelloPage),
  },
  { path: '**', redirectTo: '' },
];
