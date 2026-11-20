import {
  ChangeDetectionStrategy,
  Component,
  computed,
  effect,
  inject,
  resource,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';

import { Api } from '../../api/api';
import { companySettingsGet } from '../../api/fn/settings/company-settings-get';
import { companySettingsUpdate } from '../../api/fn/settings/company-settings-update';
import type { CompanySettings } from '../../api/models/company-settings';
import { Session } from '../../core/auth/session';
import { problemMessage } from '../../core/http/problem';
import { ThemeService } from '../../core/theme/theme';
import { MotionService, type MotionPreference } from '../../shared/motion';
import { PageHeader } from '../../shared/ui/page-header';
import { ToastService } from '../../shared/ui/toast';

/** Personal preferences for everyone; company branding and rules for the administrator. */
@Component({
  selector: 'pq-settings-page',
  imports: [FormsModule, PageHeader],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './settings-page.html',
  styleUrl: './settings-page.css',
})
export class SettingsPage {
  private readonly api = inject(Api);
  private readonly toast = inject(ToastService);
  private readonly session = inject(Session);
  protected readonly theme = inject(ThemeService);
  protected readonly motion = inject(MotionService);
  protected readonly isAdmin = computed(() => this.session.hasRole('company_admin'));

  protected readonly settings = resource({ loader: () => this.api.invoke(companySettingsGet) });
  protected readonly form = signal<Partial<CompanySettings>>({});
  protected readonly saving = signal(false);

  constructor() {
    effect(() => {
      const value = this.settings.value();
      if (value) this.form.set({ ...value });
    });
    // Live preview of the brand colours while the administrator edits them.
    effect(() => this.theme.applyBranding(this.form().primary_color, this.form().highlight_color));
  }

  protected patch(patch: Partial<CompanySettings>): void {
    this.form.update((f) => ({ ...f, ...patch }));
  }

  protected setMotion(value: MotionPreference): void {
    this.motion.setPreference(value);
  }

  protected async save(): Promise<void> {
    const f = this.form();
    this.saving.set(true);
    try {
      const saved = await this.api.invoke(companySettingsUpdate, {
        body: {
          legal_name: f.legal_name,
          timezone: f.timezone,
          primary_color: f.primary_color,
          highlight_color: f.highlight_color,
          default_radius_m: f.default_radius_m,
          approval_levels: f.approval_levels,
          wifi_check_enabled: f.wifi_check_enabled,
          break_checkins_enabled: f.break_checkins_enabled,
          retention_checkins_years: f.retention_checkins_years,
          retention_gps_months: f.retention_gps_months,
        },
      });
      this.settings.set(saved);
      const user = this.session.user();
      if (user?.company) {
        this.session.user.set({
          ...user,
          company: {
            ...user.company,
            primary_color: saved.primary_color ?? user.company.primary_color,
            highlight_color: saved.highlight_color ?? user.company.highlight_color,
          },
        });
      }
      this.toast.success('Paramètres enregistrés.');
    } catch (err) {
      this.toast.error(problemMessage(err));
    } finally {
      this.saving.set(false);
    }
  }
}
