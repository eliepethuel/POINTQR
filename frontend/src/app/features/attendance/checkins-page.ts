import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, resource, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { Api } from '../../api/api';
import { checkinsList } from '../../api/fn/checkins/checkins-list';
import type { ResultEnum } from '../../api/models/result-enum';
import { RevealOnScroll, Shimmer } from '../../shared/motion';
import { EmptyState } from '../../shared/ui/empty-state';
import { PageHeader } from '../../shared/ui/page-header';

const MODE_LABELS: Record<string, string> = {
  A: 'Borne',
  B: 'QR perso',
  C: 'Badge',
  D: 'QR imprimé',
};

/** Check-ins and fraud anomalies (EF-21): every refusal with its reason. */
@Component({
  selector: 'pq-checkins-page',
  imports: [DatePipe, FormsModule, PageHeader, EmptyState, RevealOnScroll, Shimmer],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <pq-page-header
      title="Pointages"
      eyebrow="Suivi"
      subtitle="Heure serveur, mode et motif de chaque refus."
    />
    <div class="pq-toolbar">
      <div class="segmented" role="radiogroup" aria-label="Filtre">
        @for (f of filters; track f.value) {
          <button type="button" [class.on]="result() === f.value" (click)="result.set(f.value)">
            {{ f.label }}
          </button>
        }
      </div>
      <input
        class="pq-input"
        type="date"
        aria-label="Jour"
        [ngModel]="day()"
        (ngModelChange)="day.set($event)"
      />
    </div>
    <section class="pq-card">
      @if (rows.isLoading() && !rows.hasValue()) {
        @for (i of [1, 2, 3, 4]; track i) {
          <div class="skeleton" pqShimmer></div>
        }
      } @else {
        <table class="pq-table">
          <thead>
            <tr>
              <th>Heure</th>
              <th>Agent</th>
              <th>Sens</th>
              <th>Mode</th>
              <th>Site</th>
              <th>Résultat</th>
            </tr>
          </thead>
          <tbody>
            @for (c of rows.value()?.results ?? []; track c.id; let i = $index) {
              <tr pqRevealOnScroll [revealIndex]="i % 15">
                <td class="pq-mono">
                  {{ c.effective_ts | date: 'dd/MM HH:mm:ss' }}
                  @if (c.offline) {
                    <span class="pq-badge">hors-ligne</span>
                  }
                </td>
                <td>
                  {{ c.agent_name ?? 'Inconnu' }}
                  <span class="muted pq-mono">{{ c.employee_number }}</span>
                </td>
                <td>
                  {{
                    c.direction === 'in'
                      ? 'Entrée'
                      : c.direction === 'out'
                        ? 'Sortie'
                        : c.direction || '—'
                  }}
                </td>
                <td>{{ modeLabels[c.mode] }}</td>
                <td>{{ c.site_name ?? '—' }}</td>
                <td>
                  @switch (c.result) {
                    @case ('accepted') {
                      <span class="pq-badge pq-badge-success">accepté</span>
                    }
                    @case ('ignored') {
                      <span class="pq-badge">doublon</span>
                    }
                    @default {
                      <span class="pq-badge pq-badge-danger">{{ c.refusal_label }}</span>
                      @if (c.distance_m) {
                        <span class="muted"> à {{ c.distance_m }} m</span>
                      }
                    }
                  }
                </td>
              </tr>
            }
          </tbody>
        </table>
        @if ((rows.value()?.results ?? []).length === 0) {
          <pq-empty-state title="Aucun pointage" message="Rien sur ce filtre pour ce jour." />
        }
      }
    </section>
  `,
  styles: `
    .pq-toolbar {
      margin-bottom: 16px;
    }
    .segmented {
      display: inline-flex;
      padding: 4px;
      border-radius: 999px;
      background: var(--pq-surface-2);
    }
    .segmented button {
      border: 0;
      background: transparent;
      color: var(--pq-text-muted);
      padding: 8px 14px;
      border-radius: 999px;
      cursor: pointer;
      font: 600 0.8125rem var(--pq-font-body);
    }
    .segmented button.on {
      background: var(--pq-accent);
      color: var(--pq-accent-contrast);
    }
    .muted {
      color: var(--pq-text-muted);
      font-size: 0.8125rem;
    }
    .skeleton {
      height: 40px;
      margin: 8px 0;
    }
  `,
})
export class CheckinsPage {
  private readonly api = inject(Api);
  protected readonly modeLabels = MODE_LABELS;
  protected readonly filters: { value: ResultEnum | ''; label: string }[] = [
    { value: '', label: 'Tous' },
    { value: 'accepted', label: 'Acceptés' },
    { value: 'refused', label: 'Anomalies' },
  ];
  protected readonly result = signal<ResultEnum | ''>('');
  protected readonly day = signal(new Date().toISOString().slice(0, 10));
  protected readonly rows = resource({
    params: () => ({ result: this.result(), day: this.day() }),
    loader: ({ params }) =>
      this.api.invoke(checkinsList, {
        result: params.result || undefined,
        date: params.day || undefined,
        page_size: 200,
      }),
  });
}
