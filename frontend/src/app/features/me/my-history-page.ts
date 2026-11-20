import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, resource } from '@angular/core';
import { RouterLink } from '@angular/router';

import { Api } from '../../api/api';
import { meExport } from '../../api/fn/me/me-export';
import { meHistory } from '../../api/fn/me/me-history';
import { RevealOnScroll } from '../../shared/motion';
import { PageHeader } from '../../shared/ui/page-header';
import { STATUS_LABELS } from '../agents/agent-detail-page';

/** The agent's own data (ENF-05): history, export, contest via a correction request. */
@Component({
  selector: 'pq-my-history-page',
  imports: [DatePipe, RouterLink, PageHeader, RevealOnScroll],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <pq-page-header
      title="Mon historique"
      eyebrow="Mes données"
      subtitle="Heures fixées par le serveur. Une erreur ? Demandez une correction."
    >
      <button type="button" class="pq-btn" (click)="download()">Exporter (CSV)</button>
      <a class="pq-btn pq-btn-primary" routerLink="/app/demandes">Contester un pointage</a>
    </pq-page-header>
    <section class="pq-card">
      <table class="pq-table">
        <thead>
          <tr>
            <th>Jour</th>
            <th>Statut</th>
            <th>Entrée</th>
            <th>Sortie</th>
            <th>Retard</th>
          </tr>
        </thead>
        <tbody>
          @for (d of history.value()?.workdays ?? []; track d.id; let i = $index) {
            <tr pqRevealOnScroll [revealIndex]="i % 15">
              <td>{{ d.date | date: 'EEE d MMM' }}</td>
              <td>{{ labels[d.status] }}</td>
              <td class="pq-mono">{{ (d.first_in | date: 'HH:mm') ?? '—' }}</td>
              <td class="pq-mono">{{ (d.last_out | date: 'HH:mm') ?? '—' }}</td>
              <td class="pq-mono">{{ d.late_minutes ? d.late_minutes + ' min' : '—' }}</td>
            </tr>
          }
        </tbody>
      </table>
    </section>
  `,
})
export class MyHistoryPage {
  private readonly api = inject(Api);
  protected readonly labels = STATUS_LABELS;
  protected readonly history = resource({ loader: () => this.api.invoke(meHistory) });

  protected async download(): Promise<void> {
    const res = await this.api.invoke$Response(meExport);
    const blob =
      res.body instanceof Blob ? res.body : new Blob([res.body as BlobPart], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'mes-pointages.csv';
    a.click();
    URL.revokeObjectURL(url);
  }
}
