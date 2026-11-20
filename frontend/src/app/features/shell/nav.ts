import {
  LucideBuilding2,
  LucideCalendarClock,
  LucideChartColumn,
  LucideClipboardCheck,
  LucideFileText,
  LucideGauge,
  LucideMapPin,
  LucideMonitorSmartphone,
  LucideNetwork,
  LucideScrollText,
  LucideSettings,
  LucideSmartphone,
  LucideTimer,
  LucideUserCog,
  LucideUsers,
} from '@lucide/angular';

import type { Role } from '../../core/auth/session';

export interface NavItem {
  readonly label: string;
  readonly path: string;
  readonly icon: unknown;
  /** Empty = every authenticated company user. */
  readonly roles: readonly Role[];
  readonly section: 'suivi' | 'organisation' | 'administration';
}

const STAFF: Role[] = ['company_admin', 'hr', 'manager', 'auditor'];

export const NAV: readonly NavItem[] = [
  {
    label: 'Tableau de bord',
    path: '/app/tableau-de-bord',
    icon: LucideGauge,
    roles: STAFF,
    section: 'suivi',
  },
  { label: 'Pointages', path: '/app/pointages', icon: LucideTimer, roles: STAFF, section: 'suivi' },
  {
    label: 'Demandes',
    path: '/app/demandes',
    icon: LucideClipboardCheck,
    roles: [],
    section: 'suivi',
  },
  {
    label: 'Rapports',
    path: '/app/rapports',
    icon: LucideChartColumn,
    roles: ['company_admin', 'hr', 'auditor'],
    section: 'suivi',
  },
  {
    label: 'Agents',
    path: '/app/agents',
    icon: LucideUsers,
    roles: STAFF,
    section: 'organisation',
  },
  {
    label: 'Organigramme',
    path: '/app/organisation',
    icon: LucideNetwork,
    roles: STAFF,
    section: 'organisation',
  },
  { label: 'Sites', path: '/app/sites', icon: LucideMapPin, roles: STAFF, section: 'organisation' },
  {
    label: 'Horaires',
    path: '/app/horaires',
    icon: LucideCalendarClock,
    roles: ['company_admin', 'hr', 'auditor'],
    section: 'organisation',
  },
  {
    label: 'Bornes',
    path: '/app/bornes',
    icon: LucideMonitorSmartphone,
    roles: ['company_admin', 'auditor'],
    section: 'administration',
  },
  {
    label: 'Téléphones',
    path: '/app/telephones',
    icon: LucideSmartphone,
    roles: ['company_admin', 'hr'],
    section: 'administration',
  },
  {
    label: 'Utilisateurs',
    path: '/app/utilisateurs',
    icon: LucideUserCog,
    roles: ['company_admin'],
    section: 'administration',
  },
  {
    label: "Journal d'audit",
    path: '/app/audit',
    icon: LucideScrollText,
    roles: ['company_admin', 'auditor'],
    section: 'administration',
  },
  {
    label: 'Paramètres',
    path: '/app/parametres',
    icon: LucideSettings,
    roles: [],
    section: 'administration',
  },
  {
    label: 'Mon historique',
    path: '/app/mon-historique',
    icon: LucideFileText,
    roles: ['agent'],
    section: 'suivi',
  },
];

export const PLATFORM_NAV: readonly NavItem[] = [
  {
    label: 'Entreprises',
    path: '/plateforme',
    icon: LucideBuilding2,
    roles: [],
    section: 'administration',
  },
];

export const SECTION_LABELS: Record<NavItem['section'], string> = {
  suivi: 'Suivi',
  organisation: 'Organisation',
  administration: 'Administration',
};
