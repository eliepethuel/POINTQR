import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  signal,
} from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import {
  LucideDynamicIcon,
  LucideLogOut,
  LucideMoon,
  LucidePanelLeft,
  LucideSun,
} from '@lucide/angular';

import { Session } from '../../core/auth/session';
import { ThemeService } from '../../core/theme/theme';
import { Toaster } from '../../shared/ui/toast';
import { CommandPalette } from './command-palette';
import { NAV, type NavItem, PLATFORM_NAV, SECTION_LABELS } from './nav';

const COLLAPSE_KEY = 'pq.sidebar';

@Component({
  selector: 'pq-app-shell',
  imports: [
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    LucideDynamicIcon,
    LucideLogOut,
    LucideMoon,
    LucideSun,
    LucidePanelLeft,
    Toaster,
    CommandPalette,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './app-shell.html',
  styleUrl: './app-shell.css',
})
export class AppShell {
  protected readonly session = inject(Session);
  protected readonly theme = inject(ThemeService);
  protected readonly collapsed = signal(this.readCollapsed());
  protected readonly mobileOpen = signal(false);

  protected readonly sections = computed(() => {
    const items: readonly NavItem[] = this.session.isSuperadmin()
      ? PLATFORM_NAV
      : NAV.filter((i) => i.roles.length === 0 || this.session.hasRole(...i.roles));
    const order: NavItem['section'][] = ['suivi', 'organisation', 'administration'];
    return order
      .map((s) => ({ label: SECTION_LABELS[s], items: items.filter((i) => i.section === s) }))
      .filter((s) => s.items.length > 0);
  });

  protected readonly flatItems = computed(() => this.sections().flatMap((s) => s.items));

  protected readonly initials = computed(() => {
    const name = this.session.user()?.display_name || this.session.user()?.username || '?';
    return name
      .split(/\s+/)
      .slice(0, 2)
      .map((p) => p[0]?.toUpperCase() ?? '')
      .join('');
  });

  constructor() {
    effect(() => {
      const company = this.session.company();
      this.theme.applyBranding(company?.primary_color, company?.highlight_color);
    });
  }

  protected toggleCollapse(): void {
    this.collapsed.update((v) => !v);
    try {
      localStorage.setItem(COLLAPSE_KEY, this.collapsed() ? '1' : '0');
    } catch {
      /* not persisted */
    }
  }

  protected toggleTheme(event: MouseEvent): void {
    this.theme.toggle({ x: event.clientX, y: event.clientY });
  }

  private readCollapsed(): boolean {
    try {
      return localStorage.getItem(COLLAPSE_KEY) === '1';
    } catch {
      return false;
    }
  }
}
