import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  DestroyRef,
  inject,
  resource,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';

import { Api } from '../../api/api';
import { reportsCreate } from '../../api/fn/reports/reports-create';
import { reportsList } from '../../api/fn/reports/reports-list';
import type { ReportKindEnum } from '../../api/models/report-kind-enum';
import { Session } from '../../core/auth/session';
import { problemMessage } from '../../core/http/problem';
import { RevealOnScroll } from '../../shared/motion';
import { PageHeader } from '../../shared/ui/page-header';
import { ToastService } from '../../shared/ui/toast';
import { PeriodsPanel } from './periods-panel';
import { SchedulesPanel } from './schedules-panel';

const KINDS: { value: ReportKindEnum; label: string; hint: string }[] = [
  {
    value: 'punctuality',
    label: 'Ponctualité',
    hint: 'Retards, minutes cumulées, départs anticipés, absences (Excel)',
  },
  {
    value: 'monthly_sheet',
    label: 'Feuilles de présence',
    hint: 'Une page signable par agent (PDF)',
  },
  {
    value: 'payroll',
    label: 'Éléments de paie',
    hint: 'Variables pour le logiciel de paie (Excel)',
  },
  {
    value: 'checkins',
    label: 'Pointages bruts',
    hint: 'Toutes les lignes, avec mode et motif (CSV)',
  },
  {
    value: 'badges',
    label: 'Badges QR',
    hint: 'Planche de cartes à imprimer pour le mode C (PDF)',
  },
];

function monthRange(): { start: string; end: string } {
  const now = new Date();
  const first = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  const last = new Date(now.getFullYear(), now.getMonth(), 0);
  const iso = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  return { start: iso(first), end: iso(last) };
}

/** Reports in one click, generated in the background with live progress (EF-34 to EF-36). */
@Component({
  selector: 'pq-reports-page',
  imports: [DatePipe, FormsModule, PageHeader, PeriodsPanel, RevealOnScroll, SchedulesPanel],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <pq-page-header
      title="Rapports"
      eyebrow="Suivi"
      subtitle="Générés en arrière-plan : vous pouvez continuer à travailler."
    />
    <form class="pq-card form" (ngSubmit)="generate()">
      <div class="kinds" role="radiogroup" aria-label="Type de rapport">
        @for (k of kinds; track k.value) {
          <label class="kind" [class.on]="kind === k.value">
            <input type="radio" name="kind" [value]="k.value" [(ngModel)]="kind" />
            <strong>{{ k.label }}</strong><span>{{ k.hint }}</span>
          </label>
        }
      </div>
      @if (kind !== 'badges') {
        <div class="dates">
          <label class="pq-field"
            ><span class="pq-label">Du</span
            ><input class="pq-input" type="date" name="start" [(ngModel)]="start"
          /></label>
          <label class="pq-field"
            ><span class="pq-label">Au</span
            ><input class="pq-input" type="date" name="end" [(ngModel)]="end"
          /></label>
        </div>
      }
      <button type="submit" class="pq-btn pq-btn-highlight" [disabled]="busy()">Générer</button>
    </form>

    <section class="pq-card">
      <h2>Derniers rapports</h2>
      @for (job of jobs.value()?.results ?? []; track job.id; let i = $index) {
        <article class="job" pqRevealOnScroll [revealIndex]="i">
          <div class="meta">
            <strong>{{ label(job.kind) }}</strong>
            <span class="muted"
              >{{ job.start | date: 'dd/MM/yyyy' }} → {{ job.end | date: 'dd/MM/yyyy' }} · demandé
              {{ job.created_at | date: 'dd/MM HH:mm' }}</span
            >
          </div>
          @switch (job.status) {
            @case ('done') {
              <a class="pq-btn pq-btn-primary pq-btn-sm" [href]="job.download_url">Télécharger</a>
              <span class="muted pq-mono">{{ (job.duration_ms ?? 0) / 1000 }} s</span>
            }
            @case ('failed') {
              <span class="pq-badge pq-badge-danger" [title]="job.error ?? ''">échec</span>
            }
            @default {
              <div
                class="bar"
                role="progressbar"
                [attr.aria-valuenow]="job.progress"
                aria-valuemin="0"
                aria-valuemax="100"
              >
                <span [style.transform]="'scaleX(' + (job.progress ?? 0) / 100 + ')'"></span>
              </div>
            }
          }
        </article>
      }
    </section>

    <div class="panels">
      <pq-schedules-panel [kinds]="scheduledKinds" />
      @if (canClose()) {
        <pq-periods-panel />
      }
    </div>
  `,
  styles: `
    .panels {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(min(100%, 420px), 1fr));
      gap: 20px;
      margin-top: 20px;
    }
    .form {
      display: grid;
      gap: 16px;
      margin-bottom: 20px;
    }
    .kinds {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: 10px;
    }
    .kind {
      display: grid;
      gap: 4px;
      padding: 14px;
      border-radius: 14px;
      border: 1px solid var(--pq-border);
      cursor: pointer;
      transition:
        transform var(--pq-dur-base) var(--pq-ease-out-back),
        border-color var(--pq-dur-base);
    }
    .kind input {
      position: absolute;
      opacity: 0;
      pointer-events: none;
    }
    .kind span {
      color: var(--pq-text-muted);
      font-size: 0.8125rem;
    }
    .kind.on {
      border-color: var(--pq-accent);
      transform: translateY(-2px);
      background: rgb(124 92 255 / 0.08);
    }
    .dates {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
    }
    .dates .pq-field {
      min-width: 180px;
    }
    h2 {
      margin: 0 0 12px;
      font: 600 1rem var(--pq-font-display);
    }
    .job {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px 0;
      border-bottom: 1px solid var(--pq-border);
    }
    .meta {
      flex: 1;
      display: grid;
      gap: 2px;
    }
    .muted {
      color: var(--pq-text-muted);
      font-size: 0.8125rem;
    }
    .bar {
      width: 160px;
      height: 8px;
      border-radius: 999px;
      overflow: hidden;
      background: var(--pq-surface-2);
    }
    .bar span {
      display: block;
      height: 100%;
      background: linear-gradient(90deg, var(--pq-accent), var(--pq-success));
      transform-origin: left;
      transition: transform var(--pq-dur-slow) var(--pq-ease-out-expo);
    }
  `,
})
export class ReportsPage {
  private readonly api = inject(Api);
  private readonly toast = inject(ToastService);
  private readonly session = inject(Session);
  protected readonly kinds = KINDS;
  protected readonly scheduledKinds = KINDS.filter((k) => k.value !== 'badges');
  protected readonly canClose = computed(() => this.session.hasRole('company_admin', 'hr'));
  protected kind: ReportKindEnum = 'punctuality';
  protected start = monthRange().start;
  protected end = monthRange().end;
  protected readonly busy = signal(false);
  protected readonly jobs = resource({ loader: () => this.api.invoke(reportsList, { limit: 20 }) });

  constructor() {
    // Follow progress while a job is running.
    const timer = setInterval(() => {
      if (
        (this.jobs.value()?.results ?? []).some(
          (j) => j.status === 'pending' || j.status === 'running',
        )
      ) {
        this.jobs.reload();
      }
    }, 1500);
    inject(DestroyRef).onDestroy(() => clearInterval(timer));
  }

  protected label(kind: string): string {
    return KINDS.find((k) => k.value === kind)?.label ?? kind;
  }

  protected async generate(): Promise<void> {
    this.busy.set(true);
    try {
      await this.api.invoke(reportsCreate, {
        body: {
          kind: this.kind,
          ...(this.kind === 'badges' ? {} : { start: this.start, end: this.end }),
        },
      });
      this.jobs.reload();
    } catch (err) {
      this.toast.error(problemMessage(err));
    } finally {
      this.busy.set(false);
    }
  }
}
