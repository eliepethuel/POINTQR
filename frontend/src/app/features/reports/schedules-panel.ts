import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  input,
  resource,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';

import { Api } from '../../api/api';
import { reportSchedulesCreate } from '../../api/fn/report-schedules/report-schedules-create';
import { reportSchedulesDestroy } from '../../api/fn/report-schedules/report-schedules-destroy';
import { reportSchedulesList } from '../../api/fn/report-schedules/report-schedules-list';
import { reportSchedulesPartialUpdate } from '../../api/fn/report-schedules/report-schedules-partial-update';
import type { FrequencyEnum } from '../../api/models/frequency-enum';
import type { ReportKindEnum } from '../../api/models/report-kind-enum';
import type { ReportSchedule } from '../../api/models/report-schedule';
import { Session } from '../../core/auth/session';
import { problemMessage } from '../../core/http/problem';
import { ToastService } from '../../shared/ui/toast';

const FREQUENCIES: { value: FrequencyEnum; label: string }[] = [
  { value: 'weekly', label: 'Chaque lundi (semaine écoulée)' },
  { value: 'monthly', label: 'Chaque fin de mois' },
];

/** Reports e-mailed automatically by Celery beat (EF-37). */
@Component({
  selector: 'pq-schedules-panel',
  imports: [FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="pq-card">
      <h2>Envois automatiques</h2>
      <p class="muted">Le rapport est généré puis envoyé par e-mail aux destinataires.</p>
      @if (canEdit()) {
        <form class="row" (ngSubmit)="create()">
          <label class="pq-field">
            <span class="pq-label">Rapport</span>
            <select class="pq-input" name="kind" [(ngModel)]="kind">
              @for (k of kinds(); track k.value) {
                <option [value]="k.value">{{ k.label }}</option>
              }
            </select>
          </label>
          <label class="pq-field">
            <span class="pq-label">Fréquence</span>
            <select class="pq-input" name="frequency" [(ngModel)]="frequency">
              @for (f of frequencies; track f.value) {
                <option [value]="f.value">{{ f.label }}</option>
              }
            </select>
          </label>
          <label class="pq-field grow">
            <span class="pq-label">Destinataires (séparés par des virgules)</span>
            <input
              class="pq-input"
              name="recipients"
              [(ngModel)]="recipients"
              placeholder="rh@entreprise.ci, paie@entreprise.ci"
              required
            />
          </label>
          <button type="submit" class="pq-btn pq-btn-primary" [disabled]="busy() || !recipients">
            Programmer
          </button>
        </form>
      }
      @for (s of schedules(); track s.id) {
        <article class="item">
          <div class="meta">
            <strong>{{ kindLabel(s.kind) }}</strong>
            <span class="muted">{{ frequencyLabel(s.frequency) }} · {{ recipientsOf(s) }}</span>
          </div>
          <span class="pq-badge" [class.pq-badge-success]="s.is_active !== false">
            {{ s.is_active === false ? 'en pause' : 'actif' }}
          </span>
          @if (canEdit()) {
            <button type="button" class="pq-btn pq-btn-ghost pq-btn-sm" (click)="toggle(s)">
              {{ s.is_active === false ? 'Reprendre' : 'Mettre en pause' }}
            </button>
            <button type="button" class="pq-btn pq-btn-ghost pq-btn-sm" (click)="remove(s)">
              Supprimer
            </button>
          }
        </article>
      } @empty {
        <p class="muted">Aucun envoi programmé.</p>
      }
    </section>
  `,
  styles: `
    h2 {
      margin: 0 0 6px;
      font: 600 1rem var(--pq-font-display);
    }
    .muted {
      color: var(--pq-text-muted);
      font-size: 0.8125rem;
    }
    .row {
      display: flex;
      flex-wrap: wrap;
      align-items: end;
      gap: 12px;
      margin: 12px 0;
    }
    .grow {
      flex: 1 1 260px;
    }
    .item {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
      padding: 10px 0;
      border-top: 1px solid var(--pq-border);
    }
    .meta {
      flex: 1;
      display: grid;
      gap: 2px;
    }
  `,
})
export class SchedulesPanel {
  /** Report kinds offered by the page (badges are excluded: they have no period). */
  readonly kinds = input.required<readonly { value: ReportKindEnum; label: string }[]>();
  private readonly api = inject(Api);
  private readonly toast = inject(ToastService);
  private readonly session = inject(Session);

  protected readonly frequencies = FREQUENCIES;
  protected readonly canEdit = computed(() => this.session.hasRole('company_admin', 'hr'));
  protected readonly busy = signal(false);
  protected kind: ReportKindEnum = 'punctuality';
  protected frequency: FrequencyEnum = 'monthly';
  protected recipients = '';

  private readonly list = resource({
    loader: () => this.api.invoke(reportSchedulesList, { limit: 50 }),
  });
  protected readonly schedules = computed(() => this.list.value()?.results ?? []);

  protected kindLabel(kind: string): string {
    return this.kinds().find((k) => k.value === kind)?.label ?? kind;
  }

  protected frequencyLabel(frequency: string): string {
    return FREQUENCIES.find((f) => f.value === frequency)?.label ?? frequency;
  }

  protected recipientsOf(s: ReportSchedule): string {
    return Array.isArray(s.recipients) ? s.recipients.join(', ') : '';
  }

  protected async create(): Promise<void> {
    const recipients = this.recipients
      .split(/[,;\s]+/)
      .map((r) => r.trim())
      .filter(Boolean);
    await this.run(async () => {
      await this.api.invoke(reportSchedulesCreate, {
        body: { kind: this.kind, frequency: this.frequency, recipients, is_active: true },
      });
      this.recipients = '';
    }, 'Envoi programmé.');
  }

  protected toggle(s: ReportSchedule): Promise<void> {
    return this.run(
      () =>
        this.api.invoke(reportSchedulesPartialUpdate, {
          id: s.id,
          body: { is_active: s.is_active === false },
        }),
      s.is_active === false ? 'Envoi repris.' : 'Envoi mis en pause.',
    );
  }

  protected remove(s: ReportSchedule): Promise<void> {
    return this.run(() => this.api.invoke(reportSchedulesDestroy, { id: s.id }), 'Envoi supprimé.');
  }

  private async run(action: () => Promise<unknown>, done: string): Promise<void> {
    this.busy.set(true);
    try {
      await action();
      this.toast.success(done);
      this.list.reload();
    } catch (err) {
      this.toast.error(problemMessage(err));
    } finally {
      this.busy.set(false);
    }
  }
}
