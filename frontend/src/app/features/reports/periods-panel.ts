import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  computed,
  inject,
  resource,
  signal,
} from '@angular/core';
import { FormsModule } from '@angular/forms';

import { Api } from '../../api/api';
import { periodsClose } from '../../api/fn/periods/periods-close';
import { periodsCreate } from '../../api/fn/periods/periods-create';
import { periodsList } from '../../api/fn/periods/periods-list';
import { periodsReopen } from '../../api/fn/periods/periods-reopen';
import type { Period } from '../../api/models/period';
import { Session } from '../../core/auth/session';
import { problemMessage } from '../../core/http/problem';
import { ToastService } from '../../shared/ui/toast';

function previousMonth(): string {
  const now = new Date();
  const d = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
}

/** Monthly closing for payroll (RG-14): HR closes, only the administrator reopens (traced). */
@Component({
  selector: 'pq-periods-panel',
  imports: [DatePipe, FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="pq-card">
      <h2>Clôture mensuelle</h2>
      <p class="muted">
        Une période clôturée n'accepte plus aucun pointage ni correction : clôturez-la une fois la
        paie préparée.
      </p>
      <form class="row" (ngSubmit)="close()">
        <label class="pq-field">
          <span class="pq-label">Mois</span>
          <input class="pq-input" type="month" name="month" [(ngModel)]="month" required />
        </label>
        <button type="submit" class="pq-btn pq-btn-primary" [disabled]="busy() || !month">
          Clôturer le mois
        </button>
      </form>
      @for (p of periods(); track p.id) {
        <article class="period">
          <strong>{{ p.month | date: 'MMMM yyyy' }}</strong>
          @if (p.status === 'closed') {
            <span class="pq-badge pq-badge-danger">clôturée</span>
            <span class="muted">le {{ p.closed_at | date: 'dd/MM/yyyy HH:mm' }}</span>
            @if (isAdmin()) {
              @if (reopening() === p.id) {
                <form class="reopen" (ngSubmit)="reopen(p)">
                  <input
                    class="pq-input"
                    name="reason"
                    [(ngModel)]="reason"
                    placeholder="Motif de la réouverture"
                    aria-label="Motif de la réouverture"
                    required
                  />
                  <button type="submit" class="pq-btn pq-btn-sm" [disabled]="busy() || !reason">
                    Confirmer
                  </button>
                </form>
              } @else {
                <button
                  type="button"
                  class="pq-btn pq-btn-ghost pq-btn-sm"
                  (click)="reopening.set(p.id)"
                >
                  Rouvrir
                </button>
              }
            }
          } @else if (closing().has(p.id)) {
            <span class="pq-badge">clôture en cours…</span>
            <span class="muted">recalcul des journées du mois, quelques minutes</span>
          } @else {
            <span class="pq-badge pq-badge-success">ouverte</span>
            @if (p.reopen_reason) {
              <span class="muted">rouverte : {{ p.reopen_reason }}</span>
            }
          }
        </article>
      } @empty {
        <p class="muted">Aucune période clôturée pour l'instant.</p>
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
    .row,
    .reopen {
      display: flex;
      flex-wrap: wrap;
      align-items: end;
      gap: 12px;
      margin: 12px 0;
    }
    .reopen {
      margin: 0 0 0 auto;
    }
    .period {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
      padding: 10px 0;
      border-top: 1px solid var(--pq-border);
    }
    .period strong {
      text-transform: capitalize;
    }
  `,
})
export class PeriodsPanel {
  private readonly api = inject(Api);
  private readonly toast = inject(ToastService);
  private readonly session = inject(Session);

  protected readonly isAdmin = computed(() => this.session.hasRole('company_admin'));
  protected readonly busy = signal(false);
  protected readonly reopening = signal<string | null>(null);
  /** Periods whose background closing job is still running. */
  protected readonly closing = signal<ReadonlySet<string>>(new Set());
  protected month = previousMonth();
  protected reason = '';

  private readonly list = resource({ loader: () => this.api.invoke(periodsList, { limit: 24 }) });
  protected readonly periods = computed(() =>
    [...(this.list.value()?.results ?? [])].sort((a, b) => b.month.localeCompare(a.month)),
  );

  constructor() {
    // The closing job runs in the background: refresh until the period is frozen.
    const timer = setInterval(() => {
      if (!this.closing().size) return;
      const closed = new Set(
        (this.list.value()?.results ?? []).filter((p) => p.status === 'closed').map((p) => p.id),
      );
      const still = new Set([...this.closing()].filter((id) => !closed.has(id)));
      if (still.size < this.closing().size) this.toast.success('Mois clôturé.');
      this.closing.set(still);
      if (still.size) this.list.reload();
    }, 3000);
    inject(DestroyRef).onDestroy(() => clearInterval(timer));
  }

  protected async close(): Promise<void> {
    const month = `${this.month}-01`;
    this.busy.set(true);
    try {
      let period = (this.list.value()?.results ?? []).find((p) => p.month === month);
      period ??= await this.api.invoke(periodsCreate, { body: { month } });
      await this.api.invoke(periodsClose, { id: period.id });
      this.closing.update((ids) => new Set(ids).add(period.id));
      this.toast.success('Clôture lancée : les journées du mois sont recalculées.');
      this.list.reload();
    } catch (err) {
      this.toast.error(problemMessage(err));
    } finally {
      this.busy.set(false);
    }
  }

  protected async reopen(period: Period): Promise<void> {
    this.busy.set(true);
    try {
      await this.api.invoke(periodsReopen, { id: period.id, body: { reason: this.reason } });
      this.toast.success('Période rouverte (inscrit au journal d’audit).');
      this.reason = '';
      this.reopening.set(null);
      this.list.reload();
    } catch (err) {
      this.toast.error(problemMessage(err));
    } finally {
      this.busy.set(false);
    }
  }
}
