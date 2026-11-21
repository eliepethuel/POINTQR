import type { Routes } from '@angular/router';

import { authGuard, guestGuard, roleGuard, superadminGuard } from './core/auth/guards';

const STAFF = ['company_admin', 'hr', 'manager', 'auditor'];

export const routes: Routes = [
  {
    path: '',
    title: 'PointQR — Le pointage qui ne ment pas.',
    loadComponent: () => import('./features/landing/landing-page').then((m) => m.LandingPage),
  },
  {
    path: 'connexion',
    title: 'Connexion · PointQR',
    canActivate: [guestGuard],
    loadComponent: () => import('./features/auth/login-page').then((m) => m.LoginPage),
  },
  {
    path: 'activation',
    title: 'Activer mon accès · PointQR',
    loadComponent: () => import('./features/auth/activation-page').then((m) => m.ActivationPage),
  },
  {
    path: 'kiosk',
    title: 'Borne · PointQR',
    loadComponent: () => import('./kiosk/kiosk-page').then((m) => m.KioskPage),
  },
  {
    path: 'agent',
    title: 'Pointer · PointQR',
    canActivate: [authGuard, roleGuard],
    data: { roles: ['agent'] },
    loadComponent: () => import('./agent/agent-page').then((m) => m.AgentPage),
  },
  {
    path: 'plateforme',
    canActivate: [authGuard, superadminGuard],
    loadComponent: () => import('./features/shell/app-shell').then((m) => m.AppShell),
    children: [
      {
        path: '',
        title: 'Console · PointQR',
        loadComponent: () =>
          import('./features/platform/platform-page').then((m) => m.PlatformPage),
      },
    ],
  },
  {
    path: 'app',
    canActivate: [authGuard],
    canActivateChild: [roleGuard],
    loadComponent: () => import('./features/shell/app-shell').then((m) => m.AppShell),
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'tableau-de-bord' },
      {
        path: 'tableau-de-bord',
        title: 'Tableau de bord · PointQR',
        data: { roles: STAFF },
        loadComponent: () =>
          import('./features/dashboard/dashboard-page').then((m) => m.DashboardPage),
      },
      {
        path: 'pointages',
        title: 'Pointages · PointQR',
        data: { roles: STAFF },
        loadComponent: () =>
          import('./features/attendance/checkins-page').then((m) => m.CheckinsPage),
      },
      {
        path: 'bornes',
        title: 'Bornes · PointQR',
        data: { roles: ['company_admin', 'auditor'] },
        loadComponent: () => import('./features/kiosks/kiosks-page').then((m) => m.KiosksPage),
      },
      {
        path: 'agents',
        title: 'Agents · PointQR',
        data: { roles: STAFF },
        loadComponent: () => import('./features/agents/agents-page').then((m) => m.AgentsPage),
      },
      {
        path: 'horaires',
        title: 'Horaires · PointQR',
        data: { roles: ['company_admin', 'hr', 'manager', 'auditor'] },
        loadComponent: () =>
          import('./features/schedules/schedules-page').then((m) => m.SchedulesPage),
      },
      {
        path: 'agents/import',
        title: 'Import des agents · PointQR',
        data: { roles: ['company_admin', 'hr'] },
        loadComponent: () => import('./features/agents/import-page').then((m) => m.ImportPage),
      },
      {
        path: 'agents/:id',
        title: 'Fiche agent · PointQR',
        data: { roles: STAFF },
        loadComponent: () =>
          import('./features/agents/agent-detail-page').then((m) => m.AgentDetailPage),
      },
      {
        path: 'organisation',
        title: 'Organigramme · PointQR',
        data: { roles: STAFF },
        loadComponent: () => import('./features/org/org-page').then((m) => m.OrgPage),
      },
      {
        path: 'sites',
        title: 'Sites · PointQR',
        data: { roles: STAFF },
        loadComponent: () => import('./features/sites/sites-page').then((m) => m.SitesPage),
      },
      {
        path: 'telephones',
        title: 'Téléphones · PointQR',
        data: { roles: ['company_admin', 'hr'] },
        loadComponent: () =>
          import('./features/devices/device-requests-page').then((m) => m.DeviceRequestsPage),
      },
      {
        path: 'utilisateurs',
        title: 'Utilisateurs · PointQR',
        data: { roles: ['company_admin'] },
        loadComponent: () => import('./features/users/users-page').then((m) => m.UsersPage),
      },
      {
        path: 'demandes',
        title: 'Demandes · PointQR',
        loadComponent: () =>
          import('./features/requests/requests-page').then((m) => m.RequestsPage),
      },
      {
        path: 'rapports',
        title: 'Rapports · PointQR',
        data: { roles: ['company_admin', 'hr', 'auditor'] },
        loadComponent: () => import('./features/reports/reports-page').then((m) => m.ReportsPage),
      },
      {
        path: 'audit',
        title: "Journal d'audit · PointQR",
        data: { roles: ['company_admin', 'auditor'] },
        loadComponent: () => import('./features/audit/audit-page').then((m) => m.AuditPage),
      },
      {
        path: 'mon-historique',
        title: 'Mon historique · PointQR',
        data: { roles: ['agent'] },
        loadComponent: () => import('./features/me/my-history-page').then((m) => m.MyHistoryPage),
      },
      {
        path: 'parametres',
        title: 'Paramètres · PointQR',
        loadComponent: () =>
          import('./features/settings/settings-page').then((m) => m.SettingsPage),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
