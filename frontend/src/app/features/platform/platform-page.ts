import { DatePipe, UpperCasePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, resource, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { Api } from '../../api/api';
import { platformCompaniesList } from '../../api/fn/platform/platform-companies-list';
import { platformCompaniesOnboard } from '../../api/fn/platform/platform-companies-onboard';
import { platformCompaniesReactivate } from '../../api/fn/platform/platform-companies-reactivate';
import { platformCompaniesSuspend } from '../../api/fn/platform/platform-companies-suspend';
import { platformStats } from '../../api/fn/platform/platform-stats';
import type { Company } from '../../api/models/company';
import type { OnboardingRequest } from '../../api/models/onboarding-request';
import { problemMessage } from '../../core/http/problem';
import { CountUp, RevealOnScroll } from '../../shared/motion';
import { Drawer } from '../../shared/ui/drawer';
import { PageHeader } from '../../shared/ui/page-header';
import { ToastService } from '../../shared/ui/toast';

const STEPS = ['Entreprise', 'Abonnement', 'Administrateur', 'Récapitulatif'] as const;

/** Names of the plans (the API gives their codes). */
const PLANS: Record<string, string> = {
  starter: 'Essentiel',
  business: 'Entreprise',
  enterprise: 'Grand compte',
};

/** Editor console: companies, subscriptions and the 4-step onboarding wizard (EF-01 to EF-04). */
@Component({
  selector: 'pq-platform-page',
  imports: [DatePipe, UpperCasePipe, FormsModule, PageHeader, Drawer, CountUp, RevealOnScroll],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './platform-page.html',
  styleUrl: './platform-page.css',
})
export class PlatformPage {
  protected readonly plans = PLANS;
  private readonly api = inject(Api);
  private readonly toast = inject(ToastService);
  protected readonly steps = STEPS;
  protected readonly stats = resource({ loader: () => this.api.invoke(platformStats) });
  protected readonly companies = resource({
    loader: () => this.api.invoke(platformCompaniesList, { limit: 200 }),
  });

  protected readonly wizardOpen = signal(false);
  protected readonly step = signal(0);
  protected readonly busy = signal(false);
  protected form: OnboardingRequest = this.empty();

  protected openWizard(): void {
    this.form = this.empty();
    this.step.set(0);
    this.wizardOpen.set(true);
  }

  protected next(): void {
    this.step.update((s) => Math.min(STEPS.length - 1, s + 1));
  }

  protected previous(): void {
    this.step.update((s) => Math.max(0, s - 1));
  }

  protected slugify(): void {
    if (!this.form.slug) {
      this.form.slug = this.form.legal_name
        .normalize('NFD')
        .replace(/[̀-ͯ]/g, '')
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, '')
        .slice(0, 40);
    }
  }

  protected async submit(): Promise<void> {
    this.busy.set(true);
    try {
      await this.api.invoke(platformCompaniesOnboard, {
        body: { ...this.form, code: this.form.code.toUpperCase() },
      });
      this.toast.success(`${this.form.legal_name} est prête : l'administrateur peut se connecter.`);
      this.wizardOpen.set(false);
      this.companies.reload();
      this.stats.reload();
    } catch (err) {
      this.toast.error(problemMessage(err));
    } finally {
      this.busy.set(false);
    }
  }

  protected async toggle(company: Company): Promise<void> {
    const suspend = company.status === 'active';
    if (
      suspend &&
      !confirm(
        `Suspendre ${company.legal_name} ? Les pointages seront bloqués, les données conservées.`,
      )
    )
      return;
    try {
      await this.api.invoke(suspend ? platformCompaniesSuspend : platformCompaniesReactivate, {
        id: company.id,
      });
      this.toast.success(suspend ? 'Entreprise suspendue.' : 'Entreprise réactivée.');
      this.companies.reload();
    } catch (err) {
      this.toast.error(problemMessage(err));
    }
  }

  private empty(): OnboardingRequest {
    return {
      legal_name: '',
      slug: '',
      code: '',
      sector: '',
      plan: 'starter',
      max_agents: 50,
      max_sites: 1,
      max_kiosks: 1,
      admin_username: 'admin',
      admin_password: '',
      admin_email: '',
    };
  }
}
