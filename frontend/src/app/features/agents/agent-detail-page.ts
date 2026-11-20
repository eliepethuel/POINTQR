import { DatePipe } from '@angular/common';
import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  input,
  resource,
  signal,
} from '@angular/core';
import { RouterLink } from '@angular/router';

import { Api } from '../../api/api';
import { agentsRetrieve } from '../../api/fn/agents/agents-retrieve';
import { workdaysList } from '../../api/fn/workdays/workdays-list';
import { workdaysSummary } from '../../api/fn/workdays/workdays-summary';
import { CountUp, RevealOnScroll } from '../../shared/motion';

export const STATUS_LABELS: Record<string, string> = {
  pending: 'En cours',
  present: 'Présent',
  late: 'En retard',
  late_justified: 'Retard justifié',
  absent: 'Absent',
  absent_justified: 'Absence justifiée',
  incomplete: 'Incomplète',
  holiday: 'Férié',
  off: 'Non travaillé',
};

function monthBounds(offset: number): { start: string; end: string; label: Date } {
  const now = new Date();
  const first = new Date(now.getFullYear(), now.getMonth() + offset, 1);
  const last = new Date(first.getFullYear(), first.getMonth() + 1, 0);
  const iso = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  return { start: iso(first), end: iso(last), label: first };
}

/** Agent file (EF-26): month history, cumulative lateness, absences. The avatar flies in from the list. */
@Component({
  selector: 'pq-agent-detail-page',
  imports: [DatePipe, RouterLink, CountUp, RevealOnScroll],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <a class="back" routerLink="/app/agents">← Agents</a>
    @if (agent.value(); as a) {
      <header class="head">
        <span class="avatar" [style.view-transition-name]="'agent-' + a.id"
          >{{ a.first_names[0] }}{{ a.last_name[0] }}</span
        >
        <div>
          <h1>{{ a.full_name }}</h1>
          <p class="muted">
            <span class="pq-mono">{{ a.employee_number }}</span> ·
            {{ a.job_title || 'Fonction non renseignée' }} · {{ a.org_unit_name || 'Sans unité' }}
          </p>
        </div>
      </header>
    }
    <div class="month-nav">
      <button
        type="button"
        class="pq-btn pq-btn-sm"
        (click)="offset.set(offset() - 1)"
        aria-label="Mois précédent"
      >
        ‹
      </button>
      <strong>{{ period().label | date: 'MMMM y' }}</strong>
      <button
        type="button"
        class="pq-btn pq-btn-sm"
        (click)="offset.set(offset() + 1)"
        [disabled]="offset() >= 0"
        aria-label="Mois suivant"
      >
        ›
      </button>
    </div>
    @if (summary.value(); as s) {
      <div class="stats">
        <div class="pq-card">
          <p class="pq-mono v" [pqCountUp]="s.present"></p>
          <p>jours présents</p>
        </div>
        <div class="pq-card">
          <p class="pq-mono v late" [pqCountUp]="s.late_count"></p>
          <p>retards · {{ s.late_minutes }} min cumulées</p>
        </div>
        <div class="pq-card">
          <p class="pq-mono v ko" [pqCountUp]="s.absences"></p>
          <p>absences ({{ s.justified_absences }} justifiées)</p>
        </div>
        <div class="pq-card">
          <p class="pq-mono v" [pqCountUp]="hours()"></p>
          <p>heures travaillées</p>
        </div>
      </div>
    }
    <section class="pq-card">
      <table class="pq-table">
        <thead>
          <tr>
            <th>Jour</th>
            <th>Statut</th>
            <th>Entrée</th>
            <th>Sortie</th>
            <th>Retard</th>
            <th>Départ anticipé</th>
          </tr>
        </thead>
        <tbody>
          @for (d of days.value()?.results ?? []; track d.id; let i = $index) {
            <tr pqRevealOnScroll [revealIndex]="i % 15">
              <td>{{ d.date | date: 'EEE d' }}</td>
              <td>
                <span class="pq-badge" [attr.data-status]="d.status">{{ labels[d.status] }}</span>
              </td>
              <td class="pq-mono">{{ (d.first_in | date: 'HH:mm') ?? '—' }}</td>
              <td class="pq-mono">{{ (d.last_out | date: 'HH:mm') ?? '—' }}</td>
              <td class="pq-mono">{{ d.late_minutes ? d.late_minutes + ' min' : '—' }}</td>
              <td class="pq-mono">
                {{ d.early_leave_minutes ? d.early_leave_minutes + ' min' : '—' }}
              </td>
            </tr>
          }
        </tbody>
      </table>
    </section>
  `,
  styles: `
    .back {
      color: var(--pq-text-muted);
      text-decoration: none;
    }
    .head {
      display: flex;
      gap: 16px;
      align-items: center;
      margin: 16px 0;
    }
    .avatar {
      display: grid;
      place-items: center;
      width: 64px;
      height: 64px;
      border-radius: 50%;
      background: var(--pq-accent);
      color: var(--pq-accent-contrast);
      font: 700 1.2rem var(--pq-font-mono);
    }
    h1 {
      margin: 0;
      font: 700 1.8rem var(--pq-font-display);
    }
    .muted {
      margin: 4px 0 0;
      color: var(--pq-text-muted);
    }
    .month-nav {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 16px;
      text-transform: capitalize;
    }
    .stats {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }
    .stats p {
      margin: 0;
      color: var(--pq-text-muted);
      font-size: 0.875rem;
    }
    .stats .v {
      font-size: 2rem;
      font-weight: 700;
      color: var(--pq-success);
    }
    .stats .v.late {
      color: var(--pq-highlight);
    }
    .stats .v.ko {
      color: var(--pq-danger);
    }
    [data-status='late'],
    [data-status='incomplete'] {
      background: rgb(212 255 58 / 0.14);
      color: var(--pq-highlight);
    }
    [data-status='absent'] {
      background: rgb(255 107 74 / 0.14);
      color: var(--pq-danger);
    }
    [data-status='present'] {
      background: rgb(61 220 151 / 0.14);
      color: var(--pq-success);
    }
  `,
})
export class AgentDetailPage {
  private readonly api = inject(Api);
  readonly id = input.required<string>();
  protected readonly labels = STATUS_LABELS;
  protected readonly offset = signal(0);
  protected readonly period = computed(() => monthBounds(this.offset()));

  protected readonly agent = resource({
    params: () => this.id(),
    loader: ({ params }) => this.api.invoke(agentsRetrieve, { id: params }),
  });
  protected readonly days = resource({
    params: () => ({ agent: this.id(), ...this.period() }),
    loader: ({ params }) =>
      this.api.invoke(workdaysList, {
        agent: params.agent,
        start: params.start,
        end: params.end,
        limit: 62,
      }),
  });
  protected readonly summary = resource({
    params: () => ({ agent: this.id(), ...this.period() }),
    loader: ({ params }) =>
      this.api.invoke(workdaysSummary, {
        agent: params.agent,
        start: params.start,
        end: params.end,
      }),
  });
  protected readonly hours = computed(() =>
    Math.round((this.summary.value()?.worked_minutes ?? 0) / 60),
  );
}
