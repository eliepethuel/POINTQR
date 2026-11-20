import { DatePipe, JsonPipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, resource, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { Api } from '../../api/api';
import { auditLogsList } from '../../api/fn/audit-logs/audit-logs-list';
import type { AuditLog } from '../../api/models/audit-log';
import { RevealOnScroll } from '../../shared/motion';
import { Drawer } from '../../shared/ui/drawer';
import { PageHeader } from '../../shared/ui/page-header';

/** Read-only audit trail (EF-41): who did what, when, from where, before/after. */
@Component({
  selector: 'pq-audit-page',
  imports: [DatePipe, JsonPipe, FormsModule, PageHeader, Drawer, RevealOnScroll],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <pq-page-header
      title="Journal d'audit"
      eyebrow="Administration"
      subtitle="En ajout seul : aucune entrée ne peut être modifiée ni supprimée."
    />
    <div class="pq-toolbar">
      <input
        class="pq-input"
        placeholder="Action (ex. checkin.corrected)"
        aria-label="Filtrer par action"
        [ngModel]="action()"
        (ngModelChange)="action.set($event)"
      />
      <input
        class="pq-input"
        type="date"
        aria-label="Jour"
        [ngModel]="day()"
        (ngModelChange)="day.set($event)"
      />
    </div>
    <section class="pq-card">
      <table class="pq-table">
        <thead>
          <tr>
            <th>Quand</th>
            <th>Qui</th>
            <th>Action</th>
            <th>Objet</th>
            <th>IP</th>
          </tr>
        </thead>
        <tbody>
          @for (e of logs.value()?.results ?? []; track e.id; let i = $index) {
            <tr
              class="pq-row-button"
              pqRevealOnScroll
              [revealIndex]="i % 15"
              (click)="selected.set(e)"
              (keydown.enter)="selected.set(e)"
              tabindex="0"
            >
              <td class="pq-mono">{{ e.created_at | date: 'dd/MM/yyyy HH:mm:ss' }}</td>
              <td>{{ e.actor_label }}</td>
              <td>
                <code class="pq-mono">{{ e.action }}</code>
              </td>
              <td>{{ e.object_label || e.object_type }}</td>
              <td class="pq-mono">{{ e.ip ?? '—' }}</td>
            </tr>
          }
        </tbody>
      </table>
    </section>
    <pq-drawer
      [open]="!!selected()"
      [title]="selected()?.action ?? ''"
      (closed)="selected.set(null)"
    >
      @if (selected(); as e) {
        <p class="muted">
          {{ e.actor_label }} · {{ e.created_at | date: 'dd/MM/yyyy HH:mm:ss' }} ·
          {{ e.user_agent }}
        </p>
        <h3>Avant</h3>
        <pre>{{ e.before | json }}</pre>
        <h3>Après</h3>
        <pre>{{ e.after | json }}</pre>
      }
    </pq-drawer>
  `,
  styles: `
    .pq-toolbar {
      margin-bottom: 16px;
    }
    pre {
      white-space: pre-wrap;
      word-break: break-word;
      padding: 12px;
      border-radius: 10px;
      background: var(--pq-surface-2);
      font: 0.8125rem var(--pq-font-mono);
    }
    h3 {
      margin: 16px 0 6px;
      font: 600 0.95rem var(--pq-font-display);
    }
    .muted {
      color: var(--pq-text-muted);
      font-size: 0.8125rem;
    }
  `,
})
export class AuditPage {
  private readonly api = inject(Api);
  protected readonly action = signal('');
  protected readonly day = signal('');
  protected readonly selected = signal<AuditLog | null>(null);
  protected readonly logs = resource({
    params: () => ({ action: this.action().trim(), day: this.day() }),
    loader: ({ params }) =>
      this.api.invoke(auditLogsList, {
        action: params.action || undefined,
        date: params.day || undefined,
        page_size: 200,
      }),
  });
}
